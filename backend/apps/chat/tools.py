"""Allowlisted agent capabilities with strict schemas and trusted identity binding."""

import json
from dataclasses import dataclass

from jsonschema import ValidationError, validate

from apps.catalog.services import get_product, search_products
from apps.knowledge.services import search_policies
from apps.orders.services import get_order


@dataclass(frozen=True)
class AgentContext:
    """Bind identity outside the LLM; HTTP session binding belongs to the API layer."""

    customer_id: int | None = None


def tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    """Build a strict JSON Schema compatible with Ollama function calling."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


TEXT = {"type": "string", "maxLength": 300}
IDENTIFIER = {"type": "integer", "minimum": 1, "maximum": 2147483647}
TOOLS = [
    tool(
        "search_products",
        "Busca produtos por nome/categoria, orçamento e disponibilidade. "
        "Para verificar produto específico indisponível use available_only=false. "
        "Orçamento considera preço atual sem PIX.",
        {
            "query": TEXT,
            "category": TEXT,
            "max_price": {"type": "number", "minimum": 0, "maximum": 1000000},
            "available_only": {"type": "boolean"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 16},
        },
        [],
    ),
    tool(
        "get_product",
        "Consulta preço, estoque, status e promoção atuais pelo ID retornado na busca.",
        {"product_id": IDENTIFIER},
        ["product_id"],
    ),
    tool(
        "get_order",
        "Consulta pedido SOMENTE do cliente já identificado na sessão. Não recebe customer_id.",
        {"order_id": IDENTIFIER},
        ["order_id"],
    ),
    tool(
        "search_policies",
        "Consulta regras e informações da loja no manual com página, seção e versão. "
        "Use para endereço, horários, pagamentos, PIX, frete, trocas, devoluções, "
        "garantia e escopo.",
        {
            "query": {**TEXT, "minLength": 2},
            "limit": {"type": "integer", "minimum": 1, "maximum": 5},
        },
        ["query"],
    ),
]
SCHEMAS = {item["function"]["name"]: item["function"]["parameters"] for item in TOOLS}


def execute_tool(name: str, arguments: dict, context: AgentContext) -> dict:
    """Reject unknown capabilities and malformed arguments before any database read."""
    if name not in SCHEMAS:
        return {"error": "unknown_tool"}
    try:
        # Reject non-JSON values, NaN and infinity before JSON Schema validation.
        json.dumps(arguments, allow_nan=False)
        validate(arguments, SCHEMAS[name])
    except (ValidationError, ValueError, TypeError):
        return {"error": "invalid_arguments"}
    if name == "search_products":
        return search_products(**arguments)
    if name == "get_product":
        return get_product(**arguments)
    if name == "get_order":
        return get_order(**arguments, customer_id=context.customer_id)
    return search_policies(**arguments)
