"""Exercise deterministic store tools with synthetic data and trusted identity."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import Product, Promotion
from apps.catalog.services import get_product, money, search_products
from apps.chat.tools import AgentContext, execute_tool
from apps.core.importing import import_bundle
from apps.orders.services import get_order
from tests.test_importing import FIXTURES


class StoreToolsTests(TestCase):
    """Validate prices, availability, bounded search and order access boundaries."""

    @classmethod
    def setUpTestData(cls) -> None:
        import_bundle(FIXTURES)

    def test_active_promotion_does_not_stack_with_pix(self) -> None:
        product = get_product(1)["product"]
        self.assertEqual(product["table_price"], "1000.00")
        self.assertEqual(product["current_price"], "900.00")
        self.assertEqual(product["pix_price"], "900.00")
        self.assertEqual(product["promotion"]["discount_percent"], "10.00")

    def test_inactive_promotion_is_not_offered(self) -> None:
        Promotion.objects.filter(pk=1).update(is_active=False)
        product = get_product(1)["product"]
        self.assertEqual(product["current_price"], "1000.00")
        self.assertEqual(product["pix_price"], "950.00")
        self.assertIsNone(product["promotion"])

    def test_money_uses_commercial_rounding(self) -> None:
        self.assertEqual(money(Decimal("1.005")), "1.01")

    def test_search_uses_discounted_budget_and_normalized_category(self) -> None:
        result = search_products(category="violão", max_price=900)
        self.assertEqual([p["id"] for p in result["products"]], [1])
        self.assertEqual(search_products(category="violão", max_price=899)["count"], 0)

    def test_unavailable_products_are_distinguished_from_missing(self) -> None:
        for pk in (2, 3, 4):
            self.assertFalse(get_product(pk)["product"]["available"])
        self.assertFalse(get_product(999)["found"])
        self.assertEqual(search_products(query="descontinuado")["count"], 0)
        self.assertEqual(search_products(query="descontinuado", available_only=False)["count"], 1)

    def test_search_is_bounded_and_reports_total(self) -> None:
        result = search_products(limit=1)
        self.assertEqual(result["count"], 2)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["products"]), 1)

    def test_order_access_is_bound_to_trusted_context(self) -> None:
        own = execute_tool("get_order", {"order_id": 1}, AgentContext(customer_id=1))
        self.assertTrue(own["found"])
        self.assertEqual(own["total_brl"], "900.00")
        for field in ("name", "email", "phone", "customer_id"):
            self.assertNotIn(field, own)
        other = execute_tool("get_order", {"order_id": 1}, AgentContext(customer_id=2))
        absent = execute_tool("get_order", {"order_id": 999}, AgentContext(customer_id=2))
        self.assertEqual(other, absent)

    def test_missing_session_does_not_query_order_records(self) -> None:
        with self.assertNumQueries(0):
            self.assertEqual(get_order(1, customer_id=None)["reason"], "customer_session_required")

    def test_estimate_is_not_treated_as_actual_receipt(self) -> None:
        result = get_order(1, customer_id=1, today=date(2026, 2, 1))
        self.assertTrue(result["estimate_in_past"])
        self.assertIsNone(result["actual_delivery_date"])
        self.assertIsNone(result["purchase_channel"])
        self.assertFalse(result["carrier_checked"])

    def test_identity_injection_and_bad_arguments_are_rejected_before_queries(self) -> None:
        cases = [
            ("get_order", {"order_id": 1, "customer_id": 2}),
            ("get_order", {"order_id": "1"}),
            ("get_order", {"order_id": 0}),
            ("get_order", {}),
            ("get_product", {"product_id": True}),
            ("search_products", {"max_price": float("nan")}),
            ("search_products", {"max_price": -1}),
            ("search_products", {"limit": 100}),
            ("search_products", {"query": "x" * 301}),
            ("search_products", {"available_only": "false"}),
            ("search_policies", {"query": ""}),
        ]
        for name, arguments in cases:
            with self.subTest(name=name, arguments=arguments), self.assertNumQueries(0):
                self.assertEqual(
                    execute_tool(name, arguments, AgentContext())["error"], "invalid_arguments"
                )

    def test_unknown_tool_cannot_execute_commands(self) -> None:
        with self.assertNumQueries(0):
            self.assertEqual(
                execute_tool("execute_sql", {"sql": "DROP TABLE"}, AgentContext()),
                {"error": "unknown_tool"},
            )

    def test_search_avoids_n_plus_one_queries(self) -> None:
        with self.assertNumQueries(2):
            search_products()

    def test_catalog_keeps_source_status(self) -> None:
        self.assertEqual(Product.objects.get(pk=3).status, "discontinued")
