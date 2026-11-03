"""Test policy extraction, replacement and retrieval with synthetic passages."""

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

from apps.knowledge.models import PolicyChunk, PolicyDocument
from apps.knowledge.services import extract_chunks, ingest_policies, search_policies
from tests.test_importing import FIXTURES


class PolicyTests(TestCase):
    """Validate page provenance and index behavior without publishing the original PDF."""

    def test_actual_pdf_parser_indexes_public_demo_fixture(self) -> None:
        result = ingest_policies(FIXTURES / "policies-demo.pdf", version="demo")
        self.assertEqual(result["pages"], 2)
        self.assertTrue(search_policies("endereço")["found"])
        self.assertIn("Rua Exemplo", search_policies("endereço")["sources"][0]["text"])
        self.assertIn("90 dias", search_policies("garantia legal")["sources"][0]["text"])

    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "policies.pdf"
        self.path.write_bytes(b"synthetic-test-source")
        self.reader = SimpleNamespace(
            is_encrypted=False,
            pages=[
                Mock(
                    extract_text=Mock(
                        return_value="2. Horário de Funcionamento\n"
                        "Sábado das 09:00 às 13:00.\nPágina 1"
                    )
                ),
                Mock(
                    extract_text=Mock(
                        return_value="4.1 Direito de Arrependimento\n"
                        "Devoluções online em até 7 dias após recebimento."
                    )
                ),
            ],
        )

    def ingest(self) -> dict:
        with patch("apps.knowledge.services.PdfReader", return_value=self.reader):
            return ingest_policies(self.path, version="test-1")

    def test_chunks_keep_page_and_section(self) -> None:
        chunks = extract_chunks(self.reader)
        self.assertEqual([c["page"] for c in chunks], [1, 2])
        self.assertIn("4.1", chunks[1]["section"])
        self.assertNotIn("Página 1", chunks[0]["text"])

    def test_index_is_idempotent_by_checksum_and_version(self) -> None:
        self.assertTrue(self.ingest()["changed"])
        self.assertFalse(self.ingest()["changed"])
        self.assertEqual(PolicyDocument.objects.count(), 1)
        self.assertEqual(PolicyChunk.objects.count(), 2)

    def test_rebuild_reextracts_an_unchanged_pdf(self) -> None:
        self.ingest()
        self.reader.pages = [Mock(extract_text=Mock(return_value="3. Pagamento\nPIX disponível."))]
        with patch("apps.knowledge.services.PdfReader", return_value=self.reader):
            result = ingest_policies(self.path, version="test-1", force=True)
        self.assertTrue(result["changed"])
        self.assertEqual(PolicyChunk.objects.count(), 1)

    def test_cli_import_accepts_document_version(self) -> None:
        output = StringIO()
        with patch("apps.knowledge.services.PdfReader", return_value=self.reader):
            call_command(
                "ingest_policies", str(self.path), document_version="test-1", stdout=output
            )
        self.assertIn("pages=2", output.getvalue())

    def test_retrieval_handles_accents_and_synonyms_with_provenance(self) -> None:
        self.ingest()
        result = search_policies("Me arrependi, posso devolver?", limit=1)
        self.assertTrue(result["found"])
        self.assertEqual(result["sources"][0]["page"], 2)
        self.assertEqual(result["sources"][0]["version"], "test-1")
        self.assertEqual(search_policies("horario de sabado", limit=1)["sources"][0]["page"], 1)

    def test_missing_and_unmatched_knowledge_return_no_fabricated_evidence(self) -> None:
        self.assertEqual(search_policies("endereço")["reason"], "policies_not_indexed")
        self.ingest()
        self.assertEqual(search_policies("astronomia xyz")["sources"], [])

    def test_changed_pdf_replaces_old_chunks(self) -> None:
        self.ingest()
        self.path.write_bytes(b"updated-source")
        self.reader.pages = [Mock(extract_text=Mock(return_value="3. Pagamento\nPIX disponível."))]
        self.assertTrue(self.ingest()["changed"])
        self.assertEqual(PolicyChunk.objects.count(), 1)
        self.assertEqual(search_policies("arrependimento")["sources"], [])

    def test_failed_replacement_rolls_back_document_and_chunks(self) -> None:
        self.ingest()
        original_checksum = PolicyDocument.objects.get().sha256
        self.path.write_bytes(b"updated-source")
        with (
            patch("apps.knowledge.services.PdfReader", return_value=self.reader),
            patch.object(PolicyChunk.objects, "bulk_create", side_effect=IntegrityError("failure")),
        ):
            with self.assertRaises(IntegrityError):
                ingest_policies(self.path, version="test-2")
        self.assertEqual(PolicyDocument.objects.get().sha256, original_checksum)
        self.assertEqual(PolicyChunk.objects.count(), 2)

    def test_empty_or_encrypted_pdf_is_rejected(self) -> None:
        for reader in [
            SimpleNamespace(is_encrypted=True, pages=[]),
            SimpleNamespace(is_encrypted=False, pages=[Mock(extract_text=Mock(return_value=""))]),
        ]:
            with (
                self.subTest(reader=reader),
                patch("apps.knowledge.services.PdfReader", return_value=reader),
            ):
                with self.assertRaises(ValueError):
                    ingest_policies(self.path, version="test")
        self.assertFalse(PolicyDocument.objects.exists())

    def test_long_passages_are_split_without_losing_words(self) -> None:
        self.reader.pages = [Mock(extract_text=Mock(return_value="regras " * 500))]
        chunks = extract_chunks(self.reader)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(sum(len(chunk["text"].split()) for chunk in chunks), 500)

    def test_contact_query_prefers_company_details_over_privacy(self) -> None:
        document = PolicyDocument.objects.create(
            key="store-policies",
            source_name="demo.pdf",
            version="test",
            sha256="a" * 64,
            page_count=2,
        )
        PolicyChunk.objects.create(
            document=document,
            position=0,
            page=1,
            section="9. Privacidade",
            text="Endereço é um dado pessoal.",
        )
        PolicyChunk.objects.create(
            document=document,
            position=1,
            page=2,
            section="1.2 Dados da Empresa",
            text="Endereço da empresa: Rua Exemplo, 100.",
        )
        self.assertEqual(search_policies("Qual o endereço da loja?")["sources"][0]["page"], 2)
