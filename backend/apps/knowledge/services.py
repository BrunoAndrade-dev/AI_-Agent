"""PDF ingestion and compact lexical retrieval with inspectable source references."""

import hashlib
import math
import re
from collections import Counter
from io import BytesIO
from pathlib import Path

from django.db import transaction
from pypdf import PdfReader

from apps.catalog.services import normalize
from apps.knowledge.models import PolicyChunk, PolicyDocument

STOPWORDS = set(
    (
        "a o as os de da do das dos e em no na nos nas um uma para por com que qual quais "
        "me meu minha eu posso tem como quanto voce voces loja emporio musica funciona custa"
    ).split()
)
SYNONYMS = {
    "devolver": "devolucoes",
    "devolucao": "devolucoes",
    "arrependi": "arrependimento",
    "trocar": "trocas",
    "troca": "trocas",
    "pagar": "pagamento",
    "pagamentos": "pagamento",
    "parcelas": "parcelamento",
    "parcelar": "parcelamento",
    "aberto": "funcionamento",
    "abre": "funcionamento",
    "fecha": "funcionamento",
    "entregar": "entregas",
    "entrega": "entregas",
    "promocao": "promocoes",
    "desconto": "descontos",
    "horarios": "horario",
    "acessorio": "acessorios",
}


def terms(text: str) -> list[str]:
    """Normalize lexical terms and a small explicit set of store-domain synonyms."""
    return [
        SYNONYMS.get(token, token)
        for token in normalize(text).split()
        if token not in STOPWORDS and len(token) > 1
    ]


def extract_chunks(reader: PdfReader) -> list[dict]:
    """Split layout text at headings and page boundaries, retaining provenance.

    A heading continues onto the following page. Long sections are divided at word
    boundaries; no OCR is attempted. Large pages and PDFs are bounded by ingestion.
    """
    chunks = []
    section = "Capa"
    for number, page in enumerate(reader.pages, start=1):
        content = page.extract_text(extraction_mode="layout") or ""
        buffer = []

        def flush() -> None:
            text = " ".join(" ".join(buffer).split()).replace("\x00", "")
            words = text.split()
            while words:
                part = []
                size = 0
                while words and (size + len(words[0]) < 1500 or not part):
                    word = words.pop(0)
                    part.append(word)
                    size += len(word) + 1
                if part and " ".join(part) != section:
                    chunks.append({"page": number, "section": section, "text": " ".join(part)})
            buffer.clear()

        for line in content.splitlines():
            clean = line.strip()
            if (
                not clean
                or clean.startswith("Empório da Música Manual")
                or re.fullmatch(r"Página\s+\d+", clean)
            ):
                continue
            if re.match(r"^\d+(?:\.\d+)?\.?\s+[A-ZÀ-Ý]", line):
                flush()
                section = clean[:255]
            buffer.append(clean)
        flush()
    return chunks


def ingest_policies(
    path: Path, *, version: str, key: str = "store-policies", force: bool = False
) -> dict:
    """Replace a policy index atomically and skip an unchanged source checksum."""
    if not path.is_file() or path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("Expected an accessible PDF of at most 10 MiB.")
    if not version.strip() or len(version) > 40:
        raise ValueError("A version of 1–40 characters is required.")
    data = path.read_bytes()
    checksum = hashlib.sha256(data).hexdigest()
    existing = PolicyDocument.objects.filter(key=key).first()
    if (
        not force
        and existing
        and existing.sha256 == checksum
        and existing.version == version
        and existing.chunks.exists()
    ):
        return {"changed": False, "pages": existing.page_count, "chunks": existing.chunks.count()}
    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 100:
        raise ValueError("Expected an unencrypted PDF of 1–100 pages.")
    chunks = extract_chunks(reader)
    if not chunks:
        raise ValueError("PDF contains no extractable text; OCR is not implemented.")
    with transaction.atomic():
        document, _ = PolicyDocument.objects.update_or_create(
            key=key,
            defaults={
                "source_name": path.name,
                "version": version,
                "sha256": checksum,
                "page_count": len(reader.pages),
            },
        )
        document.chunks.all().delete()
        PolicyChunk.objects.bulk_create(
            [
                PolicyChunk(document=document, position=index, **chunk)
                for index, chunk in enumerate(chunks)
            ]
        )
    return {"changed": True, "pages": len(reader.pages), "chunks": len(chunks)}


def search_policies(query: str, limit: int = 4) -> dict:
    """Rank the small manual using BM25-style lexical scores and heading weight."""
    chunks = list(
        PolicyChunk.objects.select_related("document").filter(document__key="store-policies")
    )
    if not chunks:
        return {"found": False, "reason": "policies_not_indexed", "sources": []}
    tokens = set(terms(query))
    corpus = [Counter(terms(chunk.text)) for chunk in chunks]
    average = sum(sum(counter.values()) for counter in corpus) / len(corpus) or 1
    scored = []
    for chunk, counts in zip(chunks, corpus):
        length = sum(counts.values())
        score = 0.0
        for token in tokens:
            frequency = counts[token]
            if not frequency:
                continue
            occurrences = sum(token in other for other in corpus)
            inverse = math.log(1 + (len(corpus) - occurrences + 0.5) / (occurrences + 0.5))
            score += (
                inverse * frequency * 2.2 / (frequency + 1.2 * (0.25 + 0.75 * length / average))
            )
            if token in terms(chunk.section):
                score += 2
        # The manual repeats "endereço" in its privacy chapter. Prefer the
        # company-information section for contact/location questions, not privacy.
        if tokens & {"endereco", "telefone", "contato", "whatsapp", "email"}:
            if chunk.section.startswith("1.2 "):
                score += 5
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda item: (-item[0], item[1].position))
    return {
        "found": bool(scored),
        "sources": [
            {
                "source": chunk.document.source_name,
                "version": chunk.document.version,
                "page": chunk.page,
                "section": chunk.section,
                "text": chunk.text,
            }
            for _, chunk in scored[:limit]
        ],
    }
