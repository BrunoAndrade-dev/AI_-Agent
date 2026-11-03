"""Small bounded tool-calling loop, independent from HTTP views and UI."""

import json
from dataclasses import dataclass, field

from django.db import DatabaseError
from django.utils import timezone

from apps.chat.ollama import ModelUnavailable, OllamaClient
from apps.chat.prompts import SYSTEM_PROMPT
from apps.chat.tools import TOOLS, AgentContext, execute_tool


@dataclass
class AgentReply:
    """Return text, verified evidence references and an operational outcome."""

    text: str
    status: str = "ok"
    sources: list[dict] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)


class StoreAgent:
    """Keep an in-memory conversation bound to a single trusted customer scope."""

    def __init__(self, *, context: AgentContext | None = None, client: OllamaClient | None = None):
        self.context = context or AgentContext()
        self.client = client or OllamaClient()
        self.history: list[dict] = []

    def reply(self, text: str) -> AgentReply:
        """Handle one message with a maximum of four model rounds/eight tool calls.

        Only successful user/assistant pairs enter history; previous tool messages
        are not retained, so operational facts must be refreshed on subsequent turns.
        """
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            return AgentReply("Envie uma mensagem entre 1 e 2.000 caracteres.", "invalid_input")
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
        try:
            for _ in range(4):
                message = self.client.chat(messages, TOOLS)
                calls = message.get("tool_calls", [])
                if not isinstance(calls, list):
                    raise ModelUnavailable("Malformed tool calls.")
                if not calls:
                    answer = message.get("content", "")
                    if not isinstance(answer, str) or not answer.strip() or len(answer) > 12000:
                        raise ModelUnavailable("Invalid answer.")
                    self.history.extend(
                        [
                            {"role": "user", "content": text},
                            {"role": "assistant", "content": answer},
                        ]
                    )
                    self.history = self.history[-8:]
                    return AgentReply(answer, sources=sources, tools_used=tools_used)
                if len(tools_used) + len(calls) > 8:
                    break
                messages.append(message)
                for call in calls:
                    function = call.get("function", {}) if isinstance(call, dict) else {}
                    if not isinstance(function, dict):
                        raise ModelUnavailable("Malformed tool call.")
                    name = function.get("name")
                    arguments = function.get("arguments", {})
                    if not isinstance(name, str) or not isinstance(arguments, dict):
                        raise ModelUnavailable("Malformed tool arguments.")
                    result = execute_tool(name, arguments, self.context)
                    tools_used.append(name)
                    for source in result.get("sources", []):
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
                        return AgentReply(
                            "A consulta ficou extensa. "
                            "Pode restringir a busca ou fazer uma pergunta por vez?",
                            "context_limit",
                        )
        except ModelUnavailable:
            return AgentReply(
                "O modelo local está indisponível no momento. Tente novamente em instantes.",
                "model_unavailable",
            )
        except DatabaseError:
            return AgentReply(
                "Não consegui consultar as informações da loja agora. "
                "Tente novamente em instantes.",
                "data_unavailable",
            )
        return AgentReply(
            "Não consegui concluir essa consulta com segurança. Pode reformular sua pergunta?",
            "tool_limit",
        )
