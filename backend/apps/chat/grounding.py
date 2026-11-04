"""Conservative checks for current-turn evidence, not a semantic truth verifier."""

import re
from decimal import Decimal

GREETING = "Olá! Sou o assistente da Empório da Música. Como posso ajudar?"
OUT_OF_SCOPE = "Posso ajudar com instrumentos e atendimento da Empório da Música."
CLARIFICATION = "Pode esclarecer qual instrumento, pedido ou informação da loja você procura?"
SAFE_REPLIES = {GREETING, OUT_OF_SCOPE, CLARIFICATION}

MONEY = re.compile(r"R\$\s*([-+]?\d+(?:\.\d+)*(?:,\d+)?)", re.IGNORECASE)
PRICE_FIELDS = {"table_price", "current_price", "pix_price", "total_brl"}


def monetary_values(text: str) -> set[Decimal]:
    """Read explicitly BRL-labelled amounts in Brazilian or decimal notation."""
    values: set[Decimal] = set()
    for raw in MONEY.findall(text):
        if "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif "." in raw and len(raw.rsplit(".", 1)[1]) == 3:
            raw = raw.replace(".", "")
        try:
            values.add(Decimal(raw))
        except ArithmeticError:
            # An invalid BRL literal must not silently bypass the check.
            values.add(Decimal("-1"))
    return values


def evidence_prices(results: list[dict]) -> set[Decimal]:
    """Collect quoted prices and amounts explicitly present in retrieved passages."""
    values: set[Decimal] = set()

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in PRICE_FIELDS:
                    values.add(Decimal(item))
                elif key == "text" and isinstance(item, str):
                    values.update(monetary_values(item))
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(results)
    return values


def grounding_error(answer: str, results: list[dict]) -> str | None:
    """Reject unsupported text and BRL values, without full semantic validation.

    Empty searches and scoped order denials are valid lookup evidence. Tool errors
    are excluded by the caller. A price present in a result does not prove that
    prose associated it with the correct product, payment method or availability.
    """
    if answer.strip() in SAFE_REPLIES and not results:
        return None
    if not results:
        return "missing_evidence"
    if monetary_values(answer) - evidence_prices(results):
        return "unsupported_price"
    return None
