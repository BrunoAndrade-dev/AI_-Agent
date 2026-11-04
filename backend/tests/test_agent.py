"""Test orchestration using explicit model doubles, not real-model quality claims."""

import json
from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, Mock, patch
from urllib.error import URLError

from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase

from apps.chat.agent import StoreAgent
from apps.chat.grounding import GREETING, OUT_OF_SCOPE, grounding_error, monetary_values
from apps.chat.ollama import (
    InvalidModelResponse,
    LocalOnlyRedirectHandler,
    ModelUnavailable,
    OllamaClient,
)
from apps.chat.tools import TOOLS, AgentContext, available_tools, execute_tool
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
            call("get_order", {"order_id": 1}),
            {"role": "assistant", "content": "Não encontrei esse pedido nesta sessão."},
        ]
        reply = StoreAgent(client=client, context=AgentContext(customer_id=2)).reply(
            "Quero o pedido 1"
        )
        messages = client.chat.call_args_list[1].args[0]
        tool_results = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        self.assertEqual(tool_results[0]["error"], "invalid_arguments")
        self.assertFalse(tool_results[1]["found"])
        self.assertEqual(reply.status, "ok")
        self.assertEqual(reply.validation_errors, ["invalid_arguments"])

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
        reply = StoreAgent(client=client).reply("Olá")
        self.assertEqual(reply.status, "unverified_response")
        self.assertEqual(reply.validation_errors, ["invalid_model_response"] * 4)

    def test_history_is_bounded_and_keeps_conversation_context(self) -> None:
        client = Mock()
        client.chat.return_value = {"role": "assistant", "content": GREETING}
        agent = StoreAgent(client=client)
        for i in range(6):
            agent.reply(f"Mensagem {i}")
        self.assertEqual(len(agent.history), 8)
        self.assertEqual(agent.history[0]["content"], "Mensagem 2")

    def test_unconsulted_factual_text_is_rejected_and_not_saved(self) -> None:
        client = Mock()
        client.chat.return_value = {"role": "assistant", "content": "Custa R$ 299,00."}
        agent = StoreAgent(client=client)
        reply = agent.reply("Quanto custa o ukulele?")
        self.assertEqual(reply.status, "unverified_response")
        self.assertEqual(reply.validation_errors, ["missing_evidence"] * 4)
        self.assertEqual(agent.history, [])
        self.assertNotIn("299", reply.text)
        self.assertEqual(client.chat.call_count, 4)

    def test_missing_tool_can_be_repaired_with_real_lookup(self) -> None:
        client = Mock()
        client.chat.side_effect = [
            {"role": "assistant", "content": "Vou buscar o preço."},
            call("search_products", {"query": "ukulele"}),
            {"role": "assistant", "content": "R$ 400,00; PIX R$ 380,00."},
        ]
        reply = StoreAgent(client=client).reply("Qual o preço do ukulele?")
        self.assertEqual(reply.status, "ok")
        self.assertEqual(reply.validation_errors, ["missing_evidence"])
        self.assertEqual(reply.tools_used, ["search_products"])
        messages = client.chat.call_args.args[0]
        self.assertFalse(any(m.get("content") == "Vou buscar o preço." for m in messages))

    def test_invalid_call_does_not_count_as_evidence(self) -> None:
        client = Mock()
        client.chat.side_effect = [
            call("get_product", {"product_id": "5"}),
            {"role": "assistant", "content": "Custa R$ 299,00."},
            call("get_product", {"product_id": "5"}),
            {"role": "assistant", "content": "Custa R$ 299,00."},
        ]
        reply = StoreAgent(client=client).reply("Preço do produto 5")
        self.assertEqual(reply.status, "unverified_response")
        self.assertEqual(reply.tools_used, ["get_product", "get_product"])
        self.assertIn("invalid_arguments", reply.validation_errors)
        self.assertIn("missing_evidence", reply.validation_errors)

    def test_unknown_tool_is_recorded_and_can_be_corrected(self) -> None:
        client = Mock()
        client.chat.side_effect = [
            call("query_sql", {"sql": "SELECT * FROM customers"}),
            call("search_products", {"query": "ukulele"}),
            {"role": "assistant", "content": "No PIX custa R$ 380,00."},
        ]
        reply = StoreAgent(client=client).reply("Preço do ukulele")
        self.assertEqual(reply.status, "ok")
        self.assertEqual(reply.validation_errors, ["unknown_tool"])

    def test_tool_evidence_is_renewed_in_next_turn(self) -> None:
        client = Mock()
        client.chat.side_effect = [
            call("get_product", {"product_id": 1}),
            {"role": "assistant", "content": "Preço: R$ 900,00."},
            {"role": "assistant", "content": "No PIX: R$ 855,00."},
            call("get_product", {"product_id": 1}),
            {"role": "assistant", "content": "No PIX: R$ 900,00."},
        ]
        agent = StoreAgent(client=client)
        agent.reply("Preço do produto 1?")
        reply = agent.reply("E no PIX?")
        self.assertEqual(reply.status, "ok")
        self.assertEqual(reply.tools_used, ["get_product"])
        self.assertEqual(reply.validation_errors, ["missing_evidence"])
        self.assertNotIn("855", str(agent.history))

    def test_unsupported_price_is_repaired_after_consultation(self) -> None:
        client = Mock()
        client.chat.side_effect = [
            call("get_product", {"product_id": 1}),
            {"role": "assistant", "content": "No PIX custa R$ 855,00."},
            {"role": "assistant", "content": "No PIX custa R$ 900,00."},
        ]
        reply = StoreAgent(client=client).reply("Preço PIX do produto 1?")
        self.assertEqual(reply.status, "ok")
        self.assertEqual(reply.validation_errors, ["unsupported_price"])

    def test_tool_preamble_is_not_used_instead_of_call_on_next_round(self) -> None:
        client = Mock()
        message = call("get_product", {"product_id": 5})
        message["content"] = "Vou buscar o produto."
        client.chat.side_effect = [message, {"role": "assistant", "content": "R$ 400,00."}]
        StoreAgent(client=client).reply("Produto 5")
        messages = client.chat.call_args.args[0]
        assistant_call = next(m for m in messages if m.get("tool_calls"))
        self.assertEqual(assistant_call["content"], "")
        self.assertEqual(assistant_call["tool_calls"], message["tool_calls"])

    def test_model_failure_keeps_attempted_tools_and_validation_errors(self) -> None:
        client = Mock()
        client.chat.side_effect = [call("not_a_tool", {}), ModelUnavailable("private")]
        reply = StoreAgent(client=client).reply("Preço?")
        self.assertEqual(reply.status, "model_unavailable")
        self.assertEqual(reply.tools_used, ["not_a_tool"])
        self.assertEqual(reply.validation_errors, ["unknown_tool"])

    def test_empty_search_is_valid_evidence_for_no_results(self) -> None:
        client = Mock()
        client.chat.side_effect = [
            call("search_products", {"query": "inexistente"}),
            {"role": "assistant", "content": "Não encontrei esse produto na consulta."},
        ]
        self.assertEqual(StoreAgent(client=client).reply("Produto inexistente").status, "ok")

    def test_fixed_nonfactual_reply_can_skip_tools(self) -> None:
        client = Mock()
        client.chat.return_value = {"role": "assistant", "content": OUT_OF_SCOPE}
        reply = StoreAgent(client=client).reply("Escreva um minerador de criptomoedas")
        self.assertEqual(reply.status, "ok")
        self.assertEqual(reply.tools_used, [])
        self.assertEqual(client.chat.call_count, 1)

    def test_order_denial_does_not_allow_model_to_assert_global_existence(self) -> None:
        client = Mock()
        client.chat.side_effect = [
            call("get_order", {"order_id": 2}),
            {"role": "assistant", "content": "O pedido 2 pertence a outro cliente e custa R$ 400."},
        ]
        reply = StoreAgent(client=client, context=AgentContext(customer_id=1)).reply("Pedido 2?")
        self.assertEqual(reply.status, "ok")
        self.assertEqual(
            reply.text, "Não encontrei esse pedido nesta sessão. Confira o número do pedido."
        )

    def test_tool_categories_are_bound_to_catalog_without_mutating_global_schema(self) -> None:
        from apps.catalog.models import Category

        definitions = available_tools(messages=[])
        category = definitions[0]["function"]["parameters"]["properties"]["category"]
        self.assertCountEqual(category["enum"], Category.objects.values_list("name", flat=True))
        self.assertNotIn("enum", TOOLS[0]["function"]["parameters"]["properties"]["category"])
        self.assertNotIn("enum", definitions[0]["function"]["parameters"]["properties"]["query"])
        result = execute_tool(
            "search_products", {"category": "Instrumentos"}, AgentContext(), definitions=definitions
        )
        self.assertEqual(result, {"error": "invalid_arguments"})

    def test_budget_filter_cannot_be_invented_without_numeric_user_context(self) -> None:
        definitions = available_tools(
            messages=[{"role": "user", "content": "Quanto custa o ukulele?"}]
        )
        self.assertNotIn("max_price", definitions[0]["function"]["parameters"]["properties"])
        self.assertEqual(
            execute_tool(
                "search_products", {"max_price": 100}, AgentContext(), definitions=definitions
            ),
            {"error": "invalid_arguments"},
        )

    def test_numeric_candidates_come_from_user_not_model_history(self) -> None:
        definitions = available_tools(
            messages=[
                {"role": "user", "content": "Até R$ 1.000,00"},
                {"role": "assistant", "content": "Preço R$ 299,00"},
                {"role": "user", "content": "E no PIX?"},
            ]
        )
        budget = definitions[0]["function"]["parameters"]["properties"]["max_price"]
        self.assertEqual(budget["enum"], [1000.0])

    def test_product_identifiers_must_have_a_source(self) -> None:
        definitions = available_tools(
            messages=[{"role": "user", "content": "E no PIX?"}],
            product_references={1: "Violão Exemplo Nylon"},
        )
        result = execute_tool(
            "get_product", {"product_id": 12345}, AgentContext(), definitions=definitions
        )
        self.assertEqual(result, {"error": "invalid_arguments"})
        self.assertTrue(
            execute_tool("get_product", {"product_id": 1}, AgentContext(), definitions=definitions)[
                "found"
            ]
        )

    def test_name_search_keeps_only_identity_for_later_lookup(self) -> None:
        client = Mock()
        client.chat.side_effect = [
            call("search_products", {"query": "Violão Exemplo Nylon"}),
            {"role": "assistant", "content": "Violão Exemplo Nylon custa R$ 900,00."},
            call("get_product", {"product_id": 1}),
            {"role": "assistant", "content": "No PIX: R$ 900,00."},
        ]
        agent = StoreAgent(client=client)
        agent.reply("Quanto custa o Violão Exemplo Nylon?")
        reply = agent.reply("E no PIX?")
        self.assertEqual(reply.status, "ok")
        self.assertEqual(agent.product_references, {1: "Violão Exemplo Nylon"})
        definitions = client.chat.call_args.args[1]
        product_tool = next(t for t in definitions if t["function"]["name"] == "get_product")
        self.assertEqual(
            product_tool["function"]["parameters"]["properties"]["product_id"]["enum"], [1]
        )

    def add_return_policy(self) -> None:
        document = PolicyDocument.objects.create(
            key="store-policies", source_name="demo.pdf", version="1", sha256="b" * 64, page_count=1
        )
        PolicyChunk.objects.create(
            document=document,
            position=0,
            page=1,
            section="Direito de Arrependimento",
            text="Devoluções online em sete dias do recebimento real, com embalagem original.",
        )

    def test_return_eligibility_is_not_approved_by_model(self) -> None:
        self.add_return_policy()
        client = Mock()
        client.chat.side_effect = [
            call("search_policies", {"query": "devolução"}),
            {"role": "assistant", "content": "Sua devolução está aprovada!"},
        ]
        reply = StoreAgent(client=client).reply("Quero devolver meu pedido 1. Posso?")
        self.assertEqual(reply.status, "ok")
        self.assertNotIn("está aprovada", reply.text)
        self.assertIn("a compra foi online ou na loja física?", reply.text)
        self.assertIn("Em que data você recebeu o produto de fato?", reply.text)
        self.assertIn("sete dias do recebimento real", reply.text)
        self.assertIn("demo.pdf", reply.text)

    def test_order_lookup_alone_cannot_ground_return_policy(self) -> None:
        self.add_return_policy()
        client = Mock()
        client.chat.side_effect = [
            call("get_order", {"order_id": 1}),
            {"role": "assistant", "content": "Você pode devolver até a entrega estimada."},
            call("search_policies", {"query": "devolução"}),
            {"role": "assistant", "content": "Devolução aprovada."},
        ]
        reply = StoreAgent(client=client, context=AgentContext(customer_id=1)).reply(
            "Quero devolver meu pedido 1."
        )
        self.assertEqual(reply.status, "ok")
        self.assertEqual(reply.validation_errors, ["missing_policy_evidence"])
        self.assertEqual(reply.tools_used, ["get_order", "search_policies"])
        self.assertIn("não aprovar ou executar", reply.text)

    def test_order_snapshot_does_not_turn_estimate_into_actual_delivery(self) -> None:
        client = Mock()
        client.chat.side_effect = [
            call("get_order", {"order_id": 1}),
            {"role": "assistant", "content": "Pedido entregue em 2026-01-10, ainda não entregue."},
        ]
        reply = StoreAgent(client=client, context=AgentContext(customer_id=1)).reply(
            "Meu pedido 1?"
        )
        self.assertEqual(reply.status, "ok")
        self.assertIn("status registrado: Entregue", reply.text)
        self.assertIn("Total: R$ 900,00", reply.text)
        self.assertIn("Data real de recebimento: não informada", reply.text)
        self.assertIn("não confirmação de recebimento", reply.text)
        self.assertNotIn("ainda não entregue", reply.text)


class GroundingTests(SimpleTestCase):
    """Check explicit BRL evidence, including locale and punctuation edge cases."""

    def test_money_parser_accepts_supported_formats_and_trailing_punctuation(self) -> None:
        values = monetary_values("R$ 1.000,00, R$ 1000.00. R$ 900,00. R$ 380; R$ 1.000.")
        self.assertEqual(values, {Decimal("1000"), Decimal("900"), Decimal("380")})

    def test_price_in_policy_passage_can_ground_a_quote(self) -> None:
        results = [{"sources": [{"text": "Frete de R$ 35,00 abaixo de R$ 500."}]}]
        self.assertIsNone(grounding_error("O frete custa R$ 35,00.", results))
        self.assertEqual(grounding_error("Frete R$ 40,00.", results), "unsupported_price")

    def test_unparseable_money_does_not_bypass_check(self) -> None:
        self.assertEqual(
            grounding_error("Custa R$ 1.00.00.", [{"current_price": "1000.00"}]),
            "unsupported_price",
        )


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

    def test_truncated_generation_is_not_accepted_as_a_complete_answer(self) -> None:
        client = OllamaClient(model="demo")
        with (
            patch.object(
                client,
                "request",
                return_value={
                    "done_reason": "length",
                    "message": {"role": "assistant", "content": "Preço: R$ 900"},
                },
            ),
            self.assertRaises(InvalidModelResponse),
        ):
            client.chat([], [])

    def test_structured_decision_uses_tool_schema_and_returns_standard_call(self) -> None:
        client = OllamaClient(model="demo")
        decision = {"name": "get_product", "arguments": {"product_id": 5}}
        with patch.object(
            client,
            "request",
            return_value={"message": {"role": "assistant", "content": json.dumps(decision)}},
        ) as request:
            message = client.chat(
                [{"role": "user", "content": "Preço do produto 5?"}], TOOLS, select_tool=True
            )
        self.assertEqual(message["tool_calls"][0]["function"], decision)
        payload = request.call_args.args[1]
        self.assertIn("anyOf", payload["format"])
        self.assertNotIn("tools", payload)
        self.assertEqual(payload["messages"][-1]["role"], "user")

    def test_structured_decision_cannot_inject_customer_id(self) -> None:
        client = OllamaClient(model="demo")
        decision = {"name": "get_order", "arguments": {"order_id": 2, "customer_id": 2}}
        with (
            patch.object(
                client,
                "request",
                return_value={"message": {"role": "assistant", "content": json.dumps(decision)}},
            ),
            self.assertRaises(InvalidModelResponse),
        ):
            client.chat([], TOOLS, select_tool=True)

    def test_structured_nonfactual_decision_uses_fixed_text(self) -> None:
        client = OllamaClient(model="demo")
        decision = {"name": "respond", "arguments": {"kind": "out_of_scope"}}
        with patch.object(
            client,
            "request",
            return_value={"message": {"role": "assistant", "content": json.dumps(decision)}},
        ):
            message = client.chat([], TOOLS, select_tool=True)
        self.assertEqual(message, {"role": "assistant", "content": OUT_OF_SCOPE})

    def test_malformed_decisions_are_rejected(self) -> None:
        client = OllamaClient(model="demo")
        for decision in (
            "não é JSON",
            '{"name":"query_sql","arguments":{}}',
            '{"name":"get_product","arguments":{"product_id":"5"}}',
        ):
            with (
                self.subTest(decision=decision),
                patch.object(
                    client,
                    "request",
                    return_value={"message": {"role": "assistant", "content": decision}},
                ),
                self.assertRaises(InvalidModelResponse),
            ):
                client.chat([], TOOLS, select_tool=True)
