"""Regression checks for failures found with the local real-model evaluation."""

import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

from apps.chat.agent import StoreAgent
from apps.chat.ollama import InvalidModelResponse, OllamaClient
from apps.chat.tools import TOOLS, AgentContext, explicit_product_ids
from apps.core.importing import import_bundle
from apps.knowledge.models import PolicyChunk, PolicyDocument
from tests.test_agent import call
from tests.test_importing import FIXTURES


class ExplicitIdsTests(SimpleTestCase):
    def test_mandatory_lookup_cannot_be_replaced_by_clarification(self):
        client = OllamaClient(model="demo")
        decision = {"name": "respond", "arguments": {"kind": "clarification"}}
        with patch.object(
            client,
            "request",
            return_value={"message": {"role": "assistant", "content": json.dumps(decision)}},
        ) as request:
            with self.assertRaises(InvalidModelResponse):
                client.chat([], [TOOLS[1]], select_tool=True, require_tool=True)
        choices = request.call_args.args[1]["format"]["anyOf"]
        self.assertEqual(
            [choice["properties"]["name"]["const"] for choice in choices], ["get_product"]
        )

    def test_plural_ids_excludes_unlabelled_budget(self):
        self.assertEqual(explicit_product_ids("Produtos 2 e 3 até R$ 1000"), {2, 3})
        self.assertEqual(explicit_product_ids("IDs: 2, 3 e 4; produto 5"), {2, 3, 4, 5})
        self.assertEqual(explicit_product_ids("Orçamento 2000, pedido 47"), set())


class FollowupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        import_bundle(FIXTURES)

    def test_prices_are_formatted_without_invented_channel_or_stacking(self):
        client = Mock()
        client.chat.side_effect = [
            call("get_product", {"product_id": 1}),
            {"role": "assistant", "content": "R$ 900,00 no site."},
        ]
        reply = StoreAgent(client=client).reply("Preço do produto 1 no PIX?")
        self.assertEqual(reply.status, "ok")
        self.assertIn("De R$ 1000,00 por R$ 900,00", reply.text)
        self.assertIn("não acumula", reply.text)
        self.assertNotIn("no site", reply.text)

    def test_plural_ids_require_both_current_lookups(self):
        client = Mock()
        client.chat.side_effect = [
            call("get_product", {"product_id": 2}),
            {"role": "assistant", "content": "Ambos indisponíveis."},
            call("get_product", {"product_id": 3}),
            {"role": "assistant", "content": "Ambos indisponíveis."},
        ]
        reply = StoreAgent(client=client).reply("Compare os produtos 2 e 3.")
        self.assertEqual(reply.status, "ok")
        self.assertIn("missing_product_lookup", reply.validation_errors)
        self.assertIn("Status: ativo. Estoque registrado: 0", reply.text)
        self.assertIn("Status: descontinuado. Estoque registrado: 3", reply.text)
        self.assertFalse(client.chat.call_args_list[3].kwargs["select_tool"])

    def test_named_missing_id_can_return_verified_absence(self):
        client = Mock()
        client.chat.side_effect = [
            call("get_product", {"product_id": 999}),
            {"role": "assistant", "content": "Não encontrado."},
        ]
        reply = StoreAgent(client=client).reply("Existe o produto 999?")
        self.assertEqual(reply.status, "ok")
        self.assertIn("Não encontrei produtos", reply.text)

    def test_search_does_not_prove_status_of_specific_ids(self):
        client = Mock()
        client.chat.side_effect = [call("search_products", {"query": "violão"})] + [
            {"role": "assistant", "content": "Os produtos estão esgotados."}
        ] * 3
        reply = StoreAgent(client=client).reply("Compare os produtos 2 e 3.")
        self.assertEqual(reply.status, "unverified_response")
        self.assertNotIn("estão esgotados", reply.text)

    def test_budget_in_words_requests_numeric_value_without_lookup(self):
        client = Mock()
        reply = StoreAgent(client=client).reply("Procuro um violão de até mil reais.")
        self.assertIn("orçamento", reply.text)
        self.assertIn("números", reply.text)
        client.chat.assert_not_called()

    def test_mixed_order_and_return_query_repairs_lookup_and_preserves_both_answers(self):
        document = PolicyDocument.objects.create(
            key="store-policies",
            source_name="demo.pdf",
            version="1",
            sha256="c" * 64,
            page_count=1,
        )
        PolicyChunk.objects.create(
            document=document,
            position=0,
            page=1,
            section="4.1 Devolução",
            text="Devolução online em sete dias após recebimento real.",
        )
        client = Mock()
        client.chat.side_effect = [
            call("get_order", {"order_id": 1}),
            {"role": "assistant", "content": "Pedido entregue. Devolução aprovada."},
            call("search_policies", {"query": "devolução"}),
            {"role": "assistant", "content": "Devolução aprovada."},
        ]
        reply = StoreAgent(client=client, context=AgentContext(customer_id=1)).reply(
            "Qual o status do pedido 1 e as regras de devolução?"
        )
        self.assertEqual(reply.status, "ok")
        self.assertIn("status registrado: Entregue", reply.text)
        self.assertIn("sete dias", reply.text)
        self.assertNotIn("aprovada", reply.text)
        repair = client.chat.call_args_list[2]
        self.assertTrue(repair.kwargs["select_tool"])
        self.assertEqual([tool["function"]["name"] for tool in repair.args[1]], ["search_policies"])
        self.assertFalse(client.chat.call_args_list[3].kwargs["select_tool"])
