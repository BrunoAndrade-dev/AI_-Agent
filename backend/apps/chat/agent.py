"""Small bounded tool-calling loop, independent from HTTP views and UI."""

import json
import re
from dataclasses import dataclass, field

from django.db import DatabaseError
from django.utils import timezone

from apps.chat.grounding import grounding_error
from apps.chat.ollama import InvalidModelResponse, ModelUnavailable, OllamaClient
from apps.chat.prompts import REPAIR_PRICE, REQUIRE_TOOL, SYSTEM_PROMPT
from apps.chat.responses import (
    asks_about_returns,
    catalog_snapshot_reply,
    order_snapshot_reply,
    return_guidance,
    scoped_order_reply,
)
from apps.chat.tools import AgentContext, available_tools, execute_tool, explicit_product_ids


@dataclass
class AgentReply:
    """Return text, verified evidence references and an operational outcome."""

    text: str
    status: str = "ok"
    sources: list[dict] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)


class StoreAgent:
    """Keep an in-memory conversation bound to a single trusted customer scope."""

    def __init__(self, *, context: AgentContext | None = None, client: OllamaClient | None = None):
        self.context = context or AgentContext()
        self.client = client or OllamaClient()
        self.history: list[dict] = []
        self.product_references: dict[int, str] = {}

    def reply(self, text: str) -> AgentReply:
        """Handle one message with a maximum of four model rounds/eight tool calls.

        Only successful user/assistant pairs enter history; previous tool messages
        are not retained, so operational facts must be refreshed on subsequent turns.
        """
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            return AgentReply("Envie uma mensagem entre 1 e 2.000 caracteres.", "invalid_input")
        word_budget = re.search(r"\baté\s+([^.!?;]{1,60}?)\s*reais\b", text, re.I)
        if word_budget and not re.search(r"\d", word_budget[1]):
            return AgentReply(
                "Para respeitar seu orçamento, pode informar o valor em números, "
                "por exemplo, R$ 1.000?"
            )
        history = self.history[-8:]
        while sum(len(item["content"]) for item in history) > 4000:
            history = history[2:]
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
                + f"\nData local de referência: {timezone.localdate().isoformat()}.",
            },
            *history,
            {"role": "user", "content": text},
        ]
        sources = []
        tools_used = []
        results = []
        product_lookups = set()
        order_lookups = set()
        required_orders: set[int] = set()
        policy_passages = []
        validation_errors = []

        def outcome(answer: str, status: str = "ok") -> AgentReply:
            return AgentReply(answer, status, sources, tools_used, validation_errors)

        try:
            for _ in range(4):
                tools = available_tools(
                    messages=messages, product_references=self.product_references
                )
                pending_lookup = validation_errors[-1] if validation_errors else None
                required_tool = {
                    "missing_product_lookup": "get_product",
                    "missing_order_lookup": "get_order",
                    "missing_policy_evidence": "search_policies",
                }.get(pending_lookup)
                if required_tool == "get_product" and not (
                    explicit_product_ids(text) - product_lookups
                ):
                    required_tool = None
                if required_tool == "get_order" and not (required_orders - order_lookups):
                    required_tool = None
                if required_tool == "search_policies" and policy_passages:
                    required_tool = None
                if required_tool:
                    tools = [item for item in tools if item["function"]["name"] == required_tool]
                    if required_tool == "get_product" and tools:
                        tools[0]["function"]["parameters"]["properties"]["product_id"]["enum"] = (
                            sorted(explicit_product_ids(text) - product_lookups)
                        )
                try:
                    message = self.client.chat(
                        messages,
                        tools,
                        select_tool=not results or bool(required_tool),
                        require_tool=bool(required_tool),
                    )
                    calls = message.get("tool_calls", [])
                    if not isinstance(calls, list):
                        raise InvalidModelResponse("Malformed tool calls.")
                    for call in calls:
                        function = call.get("function") if isinstance(call, dict) else None
                        if (
                            not isinstance(function, dict)
                            or not isinstance(function.get("name"), str)
                            or not isinstance(function.get("arguments"), dict)
                        ):
                            raise InvalidModelResponse("Malformed tool arguments.")
                    if not calls and (
                        not isinstance(message.get("content"), str)
                        or not message["content"].strip()
                        or len(message["content"]) > 12000
                    ):
                        raise InvalidModelResponse("Invalid answer.")
                except InvalidModelResponse:
                    validation_errors.append("invalid_model_response")
                    messages[0]["content"] += "\n" + REQUIRE_TOOL
                    continue
                if not calls:
                    required_ids = explicit_product_ids(text)
                    if results and required_ids - product_lookups:
                        validation_errors.append("missing_product_lookup")
                        messages[0]["content"] += (
                            "\nConsulte get_product para CADA ID explícito antes de responder: "
                            + json.dumps(sorted(required_ids - product_lookups))
                        )
                        continue
                    required_orders = {
                        int(value) for value in re.findall(r"\bpedido\s*#?\s*(\d+)\b", text, re.I)
                    }
                    if asks_about_returns(text) and not re.search(
                        r"\b(?:status|total|rastre\w*|consult\w*|mostr\w*)\b", text, re.I
                    ):
                        required_orders = set()
                    if results and required_orders - order_lookups:
                        validation_errors.append("missing_order_lookup")
                        messages[0]["content"] += (
                            "\nConsulte get_order para os pedidos explícitos: "
                            + json.dumps(sorted(required_orders - order_lookups))
                        )
                        continue
                    # Authorization denials are phrased by code, not inferred by the model.
                    answer = (
                        scoped_order_reply(results)
                        or order_snapshot_reply(results)
                        or message.get("content", "")
                    )
                    if asks_about_returns(text) and policy_passages:
                        orders = [
                            item for item in results if "order_id" in item or "reason" in item
                        ]
                        order_text = scoped_order_reply(orders) or order_snapshot_reply(orders)
                        answer = "\n\n".join(
                            part for part in (order_text, return_guidance(policy_passages)) if part
                        )
                    error = (
                        "missing_policy_evidence"
                        if asks_about_returns(text) and not policy_passages
                        else grounding_error(answer, results)
                    )
                    if error:
                        validation_errors.append(error)
                        # Never feed rejected factual prose back as conversation evidence.
                        messages[0]["content"] += "\n" + (
                            REPAIR_PRICE
                            if error == "unsupported_price"
                            else "Execute search_policies para consultar a política de devolução."
                            if error == "missing_policy_evidence"
                            else REQUIRE_TOOL
                        )
                        continue
                    answer = catalog_snapshot_reply(results) or answer
                    if sources:
                        references = "; ".join(
                            f"{source['source']} — {source['section']}, p. {source['page']}"
                            for source in sources
                        )
                        answer += "\n\nFontes consultadas: " + references + "."
                    self.history.extend(
                        [
                            {"role": "user", "content": text},
                            {"role": "assistant", "content": answer},
                        ]
                    )
                    self.history = self.history[-8:]
                    return outcome(answer)
                if len(tools_used) + len(calls) > 8:
                    break
                # The installed Qwen template serializes Content OR ToolCalls.
                # Discard any preamble so the tool calls survive the next request.
                messages.append({**message, "content": ""})
                for call in calls:
                    function = call["function"]
                    name = function["name"]
                    arguments = function["arguments"]
                    result = execute_tool(name, arguments, self.context, definitions=tools)
                    tools_used.append(name)
                    if "error" in result:
                        validation_errors.append(result["error"])
                    else:
                        results.append(result)
                        if name == "get_product":
                            product_lookups.add(arguments["product_id"])
                        if name == "get_order":
                            order_lookups.add(arguments["order_id"])
                        products = result.get("products", [])
                        if result.get("product"):
                            products = [*products, result["product"]]
                        for product in products:
                            identifier = product["id"]
                            self.product_references.pop(identifier, None)
                            self.product_references[identifier] = product["name"]
                        # Retain identities, not stale prices/stock, with a fixed memory bound.
                        self.product_references = dict(list(self.product_references.items())[-8:])
                    for source in result.get("sources", []):
                        if source not in policy_passages:
                            policy_passages.append(source)
                        reference = {k: v for k, v in source.items() if k != "text"}
                        if reference not in sources:
                            sources.append(reference)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": name,
                            "content": json.dumps(result, ensure_ascii=False, allow_nan=False),
                        }
                    )
                    if sum(len(item.get("content", "")) for item in messages) > 16000:
                        return outcome(
                            "A consulta ficou extensa. "
                            "Pode restringir a busca ou fazer uma pergunta por vez?",
                            "context_limit",
                        )
        except ModelUnavailable:
            return outcome(
                "O modelo local está indisponível no momento. Tente novamente em instantes.",
                "model_unavailable",
            )
        except DatabaseError:
            return outcome(
                "Não consegui consultar as informações da loja agora. "
                "Tente novamente em instantes.",
                "data_unavailable",
            )
        if validation_errors:
            return outcome(
                "Não consegui confirmar uma resposta nas fontes da loja. "
                "Pode reformular sua pergunta?",
                "unverified_response",
            )
        return outcome(
            "Não consegui concluir essa consulta com segurança. Pode reformular sua pergunta?",
            "tool_limit",
        )
