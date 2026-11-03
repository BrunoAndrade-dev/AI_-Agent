"""Test orchestration using explicit model doubles, not real-model quality claims."""

import json
from io import BytesIO
from unittest.mock import MagicMock, Mock, patch
from urllib.error import URLError

from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase

from apps.chat.agent import StoreAgent
from apps.chat.ollama import LocalOnlyRedirectHandler, ModelUnavailable, OllamaClient
from apps.chat.tools import AgentContext
from apps.core.importing import import_bundle
from apps.knowledge.models import PolicyChunk, PolicyDocument
from tests.test_importing import FIXTURES


def call(name: str, arguments: dict) -> dict:
    """Construct one Ollama-compatible tool-call message."""
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"function": {"name": name, "arguments": arguments}},
        ],
    }


class AgentTests(TestCase):
    """Verify dispatch, bounded loops, context and operational failure handling."""

    @classmethod
    def setUpTestData(cls) -> None:
        import_bundle(FIXTURES)

    def test_model_tool_roundtrip_uses_actual_database_result(self) -> None:
        client = Mock()
        client.chat.side_effect = [
            call("get_product", {"product_id": 1}),
            {"role": "assistant", "content": "Preço promocional: R$ 900,00."},
        ]
        agent = StoreAgent(client=client)
        reply = agent.reply("Quanto custa o produto 1?")
        self.assertEqual(reply.tools_used, ["get_product"])
        messages = client.chat.call_args_list[1].args[0]
        result = json.loads(next(m["content"] for m in messages if m["role"] == "tool"))
        self.assertEqual(result["product"]["current_price"], "900.00")
        self.assertEqual(len(agent.history), 2)
        self.assertTrue(all(m["role"] in {"user", "assistant"} for m in agent.history))

    def test_policy_sources_are_returned_without_raw_passage(self) -> None:
        document = PolicyDocument.objects.create(
            key="store-policies", source_name="demo.pdf", version="1", sha256="a" * 64, page_count=1
        )
        PolicyChunk.objects.create(
            document=document, position=0, page=1, section="Trocas", text="Trocas em sete dias."
        )
        client = Mock()
        client.chat.side_effect = [
            call("search_policies", {"query": "trocas"}),
            {"role": "assistant", "content": "Consulte as condições de troca (p. 1)."},
        ]
        reply = StoreAgent(client=client).reply("Quais são as regras de troca?")
        self.assertEqual(reply.sources[0]["page"], 1)
        self.assertNotIn("text", reply.sources[0])

    def test_llm_cannot_override_customer_scope(self) -> None:
        client = Mock()
        client.chat.side_effect = [
            call("get_order", {"order_id": 1, "customer_id": 1}),
            {"role": "assistant", "content": "Preciso consultar seu pedido."},
        ]
        StoreAgent(client=client, context=AgentContext(customer_id=2)).reply("Quero o pedido 1")
        messages = client.chat.call_args_list[1].args[0]
        self.assertEqual(json.loads(messages[-1]["content"])["error"], "invalid_arguments")

    def test_tool_loop_has_a_hard_limit(self) -> None:
        client = Mock()
        client.chat.return_value = call("get_product", {"product_id": 1})
        agent = StoreAgent(client=client)
        self.assertEqual(agent.reply("Produto 1").status, "tool_limit")
        self.assertEqual(client.chat.call_count, 4)
        self.assertEqual(agent.history, [])

    def test_model_failure_is_explicit_not_a_fake_answer(self) -> None:
        client = Mock()
        client.chat.side_effect = ModelUnavailable("internal detail")
        reply = StoreAgent(client=client).reply("Olá")
        self.assertEqual(reply.status, "model_unavailable")
        self.assertNotIn("internal detail", reply.text)

    def test_database_failure_is_sanitized(self) -> None:
        client = Mock()
        client.chat.return_value = call("get_product", {"product_id": 1})
        with patch("apps.chat.agent.execute_tool", side_effect=DatabaseError("private data")):
            reply = StoreAgent(client=client).reply("Preço?")
        self.assertEqual(reply.status, "data_unavailable")
        self.assertNotIn("private data", reply.text)

    def test_bad_input_does_not_call_model(self) -> None:
        client = Mock()
        agent = StoreAgent(client=client)
        for text in ("", " ", "x" * 2001):
            self.assertEqual(agent.reply(text).status, "invalid_input")
        client.chat.assert_not_called()

    def test_malformed_model_function_is_handled(self) -> None:
        client = Mock()
        client.chat.return_value = {"role": "assistant", "tool_calls": [{"function": []}]}
        self.assertEqual(StoreAgent(client=client).reply("Olá").status, "model_unavailable")

    def test_history_is_bounded_and_keeps_conversation_context(self) -> None:
        client = Mock()
        client.chat.return_value = {"role": "assistant", "content": "Olá!"}
        agent = StoreAgent(client=client)
        for i in range(6):
            agent.reply(f"Mensagem {i}")
        self.assertEqual(len(agent.history), 8)
        self.assertEqual(agent.history[0]["content"], "Mensagem 2")


class OllamaAdapterTests(SimpleTestCase):
    """Check transport contracts with local doubles; no weights are downloaded."""

    def test_redirects_cannot_escape_local_origin(self) -> None:
        self.assertIsNone(
            LocalOnlyRedirectHandler().redirect_request(
                None, None, 302, "redirect", {}, "https://example.com"
            )
        )

    def test_external_origins_and_url_credentials_are_rejected(self) -> None:
        for url in (
            "https://example.com",
            "http://user:pass@localhost:11434",
            "http://ollama:11434/api",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                OllamaClient(base_url=url, model="demo")

    def test_unconfigured_model_fails_before_http(self) -> None:
        client = OllamaClient(model="")
        client.opener = Mock()
        with self.assertRaises(ModelUnavailable):
            client.chat([], [])
        client.opener.open.assert_not_called()

    def test_timeout_and_network_details_are_sanitized(self) -> None:
        client = OllamaClient(model="demo")
        client.opener = Mock()
        client.opener.open.side_effect = URLError("private address")
        with self.assertRaises(ModelUnavailable) as caught:
            client.chat([], [])
        self.assertNotIn("private address", str(caught.exception))

    def test_request_uses_tools_nonstreaming_and_timeout(self) -> None:
        client = OllamaClient(model="demo", timeout=15)
        response = MagicMock()
        response.__enter__.return_value = BytesIO(
            json.dumps({"message": {"role": "assistant", "content": "Olá"}}).encode()
        )
        client.opener = Mock()
        client.opener.open.return_value = response
        self.assertEqual(client.chat([], [])["content"], "Olá")
        request = client.opener.open.call_args.args[0]
        body = json.loads(request.data)
        self.assertFalse(body["stream"])
        self.assertFalse(body["think"])
        self.assertEqual(client.opener.open.call_args.kwargs["timeout"], 15)

    def test_invalid_protocol_response_is_rejected(self) -> None:
        client = OllamaClient(model="demo")
        with patch.object(
            client, "request", return_value={"message": {"role": "user", "content": "bad"}}
        ):
            with self.assertRaises(ModelUnavailable):
                client.chat([], [])
