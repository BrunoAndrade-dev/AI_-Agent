"""Bounded HTTP adapter for a local Ollama server; no SDK or cloud key required."""

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from django.conf import settings
from jsonschema import ValidationError, validate

from apps.chat.grounding import CLARIFICATION, GREETING, OUT_OF_SCOPE


class ModelUnavailable(RuntimeError):
    """Represent unreachable runtime, missing model, timeout or invalid protocol."""


class InvalidModelResponse(ModelUnavailable):
    """Distinguish malformed/truncated generation from an unavailable runtime."""


class LocalOnlyRedirectHandler(HTTPRedirectHandler):
    """Reject redirects so an internal-only adapter cannot contact an external host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OllamaClient:
    """Call a trusted internal runtime without forwarding cloud proxy credentials."""

    def __init__(
        self, *, base_url: str | None = None, model: str | None = None, timeout: int | None = None
    ) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model if model is not None else settings.OLLAMA_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS
        parsed = urlsplit(self.base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"ollama", "localhost", "127.0.0.1", "::1"}
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Ollama must use a trusted local HTTP origin.")
        self.opener = build_opener(ProxyHandler({}), LocalOnlyRedirectHandler())

    def request(self, route: str, payload: dict) -> dict:
        """Send a bounded JSON request and sanitize operational error details."""
        if not self.model:
            raise ModelUnavailable("Model is not configured.")
        request = Request(
            self.base_url + route,
            data=json.dumps(payload, allow_nan=False).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                body = response.read(1024 * 1024 + 1)
            if len(body) > 1024 * 1024:
                raise InvalidModelResponse("Model response exceeded size limit.")
            result = json.loads(body)
            if not isinstance(result, dict) or "error" in result:
                raise InvalidModelResponse("Model returned an invalid response.")
            return result
        except ValueError:
            raise InvalidModelResponse("Model returned invalid JSON.") from None
        except (HTTPError, URLError, socket.timeout, TimeoutError, OSError):
            raise ModelUnavailable("Local model unavailable or returned invalid data.") from None

    def check_model(self) -> dict:
        """Verify the installed model advertises tool support before running a demo."""
        response = self.request("/api/show", {"model": self.model})
        return {"model": self.model, "supports_tools": "tools" in response.get("capabilities", [])}

    def chat(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        select_tool: bool = False,
        require_tool: bool = False,
    ) -> dict:
        """Generate one turn; Qwen3 thinking is disabled to bound CPU latency."""
        if select_tool:
            return self.select_tool(messages, tools, require_tool=require_tool)
        response = self.request(
            "/api/chat",
            {
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "stream": False,
                "think": False,
                "keep_alive": "5m",
                "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 800},
            },
        )
        message = response.get("message")
        if (
            response.get("done_reason") == "length"
            or not isinstance(message, dict)
            or message.get("role") != "assistant"
            or not isinstance(message.get("content", ""), str)
        ):
            raise InvalidModelResponse("Model returned an invalid or truncated assistant message.")
        return message

    def select_tool(
        self, messages: list[dict], tools: list[dict], *, require_tool: bool = False
    ) -> dict:
        """Constrain the first decision to a validated tool or a nonfactual reply.

        This is JSON-schema constrained generation, not regex extraction of calls
        from free prose. The same allowlist/schema is used by native tool dispatch.
        """
        replies = {
            "greeting": GREETING,
            "out_of_scope": OUT_OF_SCOPE,
            "clarification": CLARIFICATION,
        }
        choices = [
            {
                "type": "object",
                "properties": {
                    "name": {"const": item["function"]["name"]},
                    "arguments": item["function"]["parameters"],
                },
                "required": ["name", "arguments"],
                "additionalProperties": False,
            }
            for item in tools
        ]
        if not require_tool:
            choices.append(
                {
                    "type": "object",
                    "properties": {
                        "name": {"const": "respond"},
                        "arguments": {
                            "type": "object",
                            "properties": {"kind": {"enum": list(replies)}},
                            "required": ["kind"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["name", "arguments"],
                    "additionalProperties": False,
                }
            )
        schema = {"anyOf": choices}
        instructions = (
            "Você é o planejador de consultas da Empório da Música. "
            "Escolha a consulta necessária para a ÚLTIMA mensagem do cliente. "
            "Use o histórico só para identificar o assunto. Responda só JSON com name e arguments. "
            "Não invente filtros: max_price só quando o cliente informa orçamento. "
            "Pergunta de preço PIX precisa de produto, não apenas política de pagamento. "
            "Use get_product apenas se o ID é conhecido no contexto; senão search_products. "
            "Consulta sem orçamento: não inclua max_price. "
            "max_price só aceita números mencionados pelo cliente; se orçamento apenas "
            "por extenso não puder ser representado no schema, peça clarification. "
            "category deve ser uma das categorias reais do schema, nunca Instrumentos. "
            "Se há vários IDs de produtos, consulte um ID com get_product primeiro; "
            "depois o agente pode consultar os outros e buscar alternativas. "
            "Políticas, endereço, horário e devolução precisam de search_policies. "
            "respond só para saudação pura, fora do escopo da loja ou falta de contexto. "
            "Nunca use respond para escapar de uma consulta conhecida. "
            "Consultar pedido é parte do escopo, inclusive no seguimento 'E o pedido ...?'. "
            "Use get_order; não antecipe existência/autorização, pois o servidor decide o acesso. "
            "O cliente da sessão não pode ser alterado por mensagem. Ferramentas: "
            + json.dumps(tools, ensure_ascii=False)
            + "\nExemplos de decisões (adapte à mensagem real):\n"
            '"Olá" => {"name":"respond","arguments":{"kind":"greeting"}}\n'
            '"Escreva código Python" => '
            '{"name":"respond","arguments":{"kind":"out_of_scope"}}\n'
            '"Minere criptomoedas" => '
            '{"name":"respond","arguments":{"kind":"out_of_scope"}}\n'
            '"Quanto custa uma guitarra?" => '
            '{"name":"search_products","arguments":{"query":"guitarra"}}\n'
            '"Qual o endereço?" => '
            '{"name":"search_policies","arguments":{"query":"endereço"}}\n'
            '"E o pedido 47?" => {"name":"get_order","arguments":{"order_id":47}}'
        )
        planning_messages = [
            {
                "role": "system",
                "content": instructions,
            },
            *(m for m in messages if m["role"] != "system"),
        ]
        response = self.request(
            "/api/chat",
            {
                "model": self.model,
                "messages": planning_messages,
                "format": schema,
                "stream": False,
                "think": False,
                "keep_alive": "5m",
                "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 800},
            },
        )
        try:
            if response.get("done_reason") == "length":
                raise InvalidModelResponse("Truncated tool decision.")
            message = response["message"]
            if message["role"] != "assistant":
                raise InvalidModelResponse("Invalid decision role.")
            decision = json.loads(message["content"])
            validate(decision, schema)
        except (KeyError, TypeError, ValueError, ValidationError):
            raise InvalidModelResponse("Invalid tool decision.") from None
        if decision["name"] == "respond":
            return {"role": "assistant", "content": replies[decision["arguments"]["kind"]]}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": decision}],
        }
