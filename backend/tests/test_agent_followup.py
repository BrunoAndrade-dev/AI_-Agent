"""Regression checks for failures found with the local real-model evaluation."""

import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

from apps.catalog.models import Category, Product
from apps.chat.agent import StoreAgent
from apps.chat.ollama import InvalidModelResponse, OllamaClient
from apps.chat.tools import TOOLS, AgentContext, available_tools, execute_tool, explicit_product_ids
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

    def test_named_product_does_not_allow_an_inferred_category_filter(self):
        Category.objects.create(id=30, name="Guitarras", description="Categoria real")
        definitions = available_tools(
            messages=[
                {"role": "user", "content": "Quanto custa o Takamine GD20? Ele está disponível?"}
            ]
        )
        self.assertNotIn("category", definitions[0]["function"]["parameters"]["properties"])
        result = execute_tool(
            "search_products",
            {"query": "Takamine GD20", "category": "Guitarras"},
            AgentContext(),
            definitions=definitions,
        )
        self.assertEqual(result, {"error": "invalid_arguments"})

    def test_explicit_instrument_type_keeps_the_matching_category(self):
        definitions = available_tools(messages=[{"role": "user", "content": "Quero um violão"}])
        schema = definitions[0]["function"]["parameters"]["properties"]["category"]
        self.assertEqual(schema["enum"], ["Violões"])

    def test_pix_promotion_rule_overrides_incorrect_model_interpretation(self):
        document = PolicyDocument.objects.create(
            key="store-policies",
            source_name="manual.pdf",
            version="2.1",
            sha256="d" * 64,
            page_count=6,
        )
        PolicyChunk.objects.create(
            document=document,
            position=0,
            page=6,
            section="6.2 Regras de Promoções",
            text=(
                "Promoções não são cumulativas. "
                "O desconto de PIX não se aplica sobre preços promocionais."
            ),
        )
        client = Mock()
        client.chat.side_effect = [
            call("search_policies", {"query": "PIX promoções cumulatividade"}),
            {"role": "assistant", "content": "PIX acumula mesmo em promoção."},
        ]
        reply = StoreAgent(client=client).reply(
            "Qual é a regra do PIX quando o produto já está em promoção?"
        )
        self.assertEqual(reply.status, "ok")
        self.assertIn("não se aplica", reply.text)
        self.assertNotIn("PIX acumula", reply.text)
        self.assertEqual(reply.sources[0]["page"], 6)
        self.assertTrue(client.chat.call_args_list[0].kwargs["require_tool"])

    def test_pix_payment_table_alone_does_not_ground_promotion_rule(self):
        document = PolicyDocument.objects.create(
            key="store-policies",
            source_name="manual.pdf",
            version="2.1",
            sha256="e" * 64,
            page_count=3,
        )
        PolicyChunk.objects.create(
            document=document,
            position=0,
            page=3,
            section="3. Pagamento",
            text="PIX: 5% de desconto sobre preço de tabela.",
        )
        client = Mock()
        client.chat.return_value = call(
            "search_policies", {"query": "PIX promoções cumulatividade"}
        )
        reply = StoreAgent(client=client).reply("O desconto PIX acumula com promoção?")
        self.assertNotEqual(reply.status, "ok")
        self.assertNotIn("PIX acumula", reply.text)

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

    def test_pix_followup_requires_fresh_lookup_of_the_only_known_product(self):
        Product.objects.filter(pk=1).update(price_brl="1200.00")
        client = Mock()
        client.chat.side_effect = [
            call("get_product", {"product_id": 1}),
            {"role": "assistant", "content": "PIX: R$ 1080,00."},
        ]
        agent = StoreAgent(client=client)
        agent.product_references = {1: "Violão Exemplo Nylon"}
        reply = agent.reply("E no PIX?")
        self.assertEqual(reply.status, "ok")
        self.assertIn("PIX: R$ 1080,00", reply.text)
        self.assertEqual(reply.tools_used, ["get_product"])
        first = client.chat.call_args_list[0]
        self.assertTrue(first.kwargs["require_tool"])
        self.assertEqual([t["function"]["name"] for t in first.args[1]], ["get_product"])

    def test_pix_followup_does_not_guess_between_multiple_or_missing_references(self):
        for references in ({}, {1: "Nylon", 5: "Concert"}):
            client = Mock()
            agent = StoreAgent(client=client)
            agent.product_references = references
            reply = agent.reply("E no PIX?")
            self.assertIn("qual instrumento", reply.text)
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
