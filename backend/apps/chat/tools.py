"""Allowlisted agent capabilities with strict schemas and trusted identity binding."""

import json
import re
from copy import deepcopy
from dataclasses import dataclass

from jsonschema import ValidationError, validate

from apps.catalog.models import Category
from apps.catalog.services import get_product, search_products
from apps.chat.grounding import monetary_values
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
            "max_price": {
                "type": "number",
                "minimum": 0,
                "maximum": 1000000,
                "description": "Teto informado pelo cliente. OMITA se não houver orçamento; "
                "nunca invente um valor padrão.",
            },
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


def explicit_product_ids(text: str) -> set[int]:
    """Read explicitly labelled IDs, including Portuguese lists, never budgets."""
    groups = re.findall(
        r"\b(?:produtos?|ids?|instrumentos?)\s*[:#]?\s*"
        r"(\d+(?:\s*(?:,|e)\s*\d+)*)\b",
        text,
        re.IGNORECASE,
    )
    return {
        int(value)
        for group in groups
        for value in re.findall(r"\d+", group)
        if 1 <= int(value) <= 2147483647
    }


def available_tools(
    *, messages: list[dict] | None = None, product_references: dict[int, str] | None = None
) -> list[dict]:
    """Bind taxonomy and numeric filter candidates to real data and user context.

    Numeric provenance limits invented defaults; it does not prove that a number
    mentioned by a customer is a budget. The planner must still interpret intent.
    """
    tools = deepcopy(TOOLS)
    categories = list(Category.objects.order_by("id").values_list("name", flat=True))
    properties = tools[0]["function"]["parameters"]["properties"]
    # TEXT is reused by query/category: deepcopy preserves that alias, so replace
    # category instead of mutating it and accidentally constraining the name query.
    category_schema = {
        **properties["category"],
        "description": "Categoria real do catálogo; omita se não souber.",
    }
    properties["category"] = category_schema
    if categories:
        category_schema["enum"] = categories
    if messages is not None:
        amounts = set()
        product_ids = set(product_references or {})
        for message in messages:
            if message["role"] == "user":
                product_ids.update(explicit_product_ids(message["content"]))
                for token in re.findall(r"(?<!\w)\d+(?:\.\d+)*(?:,\d+)?(?!\w)", message["content"]):
                    amounts.update(monetary_values("R$ " + token))
        candidates = sorted(float(amount) for amount in amounts if 0 <= amount <= 1000000)
        if candidates:
            properties["max_price"]["enum"] = candidates
        else:
            del properties["max_price"]
        if product_ids:
            tools[1]["function"]["parameters"]["properties"]["product_id"] = {
                **IDENTIFIER,
                "enum": sorted(product_ids),
            }
            if product_references:
                tools[1]["function"]["description"] += " Identificações já consultadas: " + (
                    json.dumps(product_references, ensure_ascii=False)
                )
        else:
            tools.pop(1)
    return tools


def execute_tool(
    name: str, arguments: dict, context: AgentContext, *, definitions: list[dict] | None = None
) -> dict:
    """Reject unknown capabilities and malformed arguments before any database read."""
    if name not in SCHEMAS or (
        definitions is not None
        and not any(item["function"]["name"] == name for item in definitions)
    ):
        return {"error": "unknown_tool"}
    try:
        # Reject non-JSON values, NaN and infinity before JSON Schema validation.
        json.dumps(arguments, allow_nan=False)
        schemas = (
            {item["function"]["name"]: item["function"]["parameters"] for item in definitions}
            if definitions is not None
            else SCHEMAS
        )
        validate(arguments, schemas[name])
    except (ValidationError, ValueError, TypeError):
        return {"error": "invalid_arguments"}
    if name == "search_products":
        return search_products(**arguments)
    if name == "get_product":
        return get_product(**arguments)
    if name == "get_order":
        return get_order(**arguments, customer_id=context.customer_id)
    return search_policies(**arguments)
