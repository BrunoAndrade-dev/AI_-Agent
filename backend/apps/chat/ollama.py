"""Bounded HTTP adapter for a local Ollama server; no SDK or cloud key required."""

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from django.conf import settings


class ModelUnavailable(RuntimeError):
    """Represent unreachable runtime, missing model, timeout or invalid protocol."""


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
                raise ModelUnavailable("Model response exceeded size limit.")
            result = json.loads(body)
            if not isinstance(result, dict) or "error" in result:
                raise ModelUnavailable("Model returned an invalid response.")
            return result
        except (HTTPError, URLError, socket.timeout, TimeoutError, OSError, ValueError):
            raise ModelUnavailable("Local model unavailable or returned invalid data.") from None

    def check_model(self) -> dict:
        """Verify the installed model advertises tool support before running a demo."""
        response = self.request("/api/show", {"model": self.model})
        return {"model": self.model, "supports_tools": "tools" in response.get("capabilities", [])}

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        """Generate one turn; Qwen3 thinking is disabled to bound CPU latency."""
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
            not isinstance(message, dict)
            or message.get("role") != "assistant"
            or not isinstance(message.get("content", ""), str)
        ):
            raise ModelUnavailable("Model returned an invalid assistant message.")
        return message
