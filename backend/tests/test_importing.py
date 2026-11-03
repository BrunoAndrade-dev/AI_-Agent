"""Exercise CSV ingestion and database guarantees using public synthetic inputs."""

import csv
import shutil
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from apps.catalog.models import Category, Product, Promotion
from apps.core.importing import ImportValidationError, import_bundle
from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "synthetic"


class ImportBundleTests(TestCase):
    """Verify successful imports, idempotency, validation and failure atomicity."""

    def setUp(self) -> None:
        """Copy fixtures so each test can mutate its inputs independently."""
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        for path in FIXTURES.glob("*.csv"):
            shutil.copyfile(path, self.directory / path.name)

    def edit(self, table: str, row: int, field: str, value: str) -> None:
        """Replace one source cell without changing the remaining CSV schema."""
        path = self.directory / f"{table}.csv"
        with path.open(newline="", encoding="utf-8") as source:
            reader = csv.DictReader(source)
            headers = reader.fieldnames
            rows = list(reader)
        rows[row][field] = value
        with path.open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    def test_import_preserves_ids_totals_contacts_and_optional_values(self) -> None:
        report = import_bundle(self.directory)
        self.assertEqual(report["counts"]["products"]["created"], 5)
        self.assertEqual(Customer.objects.filter(email="demo@example.invalid").count(), 2)
        self.assertEqual(Order.objects.get(pk=1).total_brl, Decimal("900.00"))
        self.assertEqual(Product.objects.get(pk=1).price_brl, Decimal("1000.00"))
        pending = Order.objects.get(pk=2)
        self.assertIsNone(pending.tracking_code)
        self.assertIsNone(pending.estimated_delivery)
        self.assertEqual(pending.notes, "")
        self.assertEqual(len(report["warnings"]), 3)

    def test_reimport_updates_without_duplicates(self) -> None:
        import_bundle(self.directory)
        self.edit("products", 0, "price_brl", "950.00")
        report = import_bundle(self.directory)
        self.assertTrue(all(counts["created"] == 0 for counts in report["counts"].values()))
        self.assertEqual(Product.objects.count(), 5)
        self.assertEqual(OrderItem.objects.count(), 2)
        self.assertEqual(Product.objects.get(pk=1).price_brl, Decimal("950.00"))
        self.assertEqual(Order.objects.get(pk=1).total_brl, Decimal("900.00"))

    def test_dry_run_does_not_create_records(self) -> None:
        report = import_bundle(self.directory, dry_run=True)
        self.assertTrue(report["dry_run"])
        self.assertFalse(Category.objects.exists())
        self.assertFalse(Order.objects.exists())

    def test_dry_run_does_not_change_existing_records(self) -> None:
        import_bundle(self.directory)
        self.edit("products", 0, "price_brl", "12.00")
        import_bundle(self.directory, dry_run=True)
        self.assertEqual(Product.objects.get(pk=1).price_brl, Decimal("1000.00"))
        self.assertTrue(Promotion.objects.get(pk=1).is_active)

    def test_invalid_values_are_rejected_before_writes(self) -> None:
        cases = [
            ("products", "price_brl", "-1"),
            ("products", "price_brl", "1.001"),
            ("products", "price_brl", "NaN"),
            ("products", "stock_quantity", "-1"),
            ("products", "stock_quantity", "1.0"),
            ("products", "status", "unknown"),
            ("products", "specs", "[]"),
            ("products", "specs", "not-json"),
            ("products", "created_at", "2026-02-30"),
            ("order_items", "quantity", "0"),
            ("promotions", "discount_percent", "101"),
            ("promotions", "is_active", "true"),
        ]
        for table, field, value in cases:
            with self.subTest(table=table, field=field, value=value):
                original = (self.directory / f"{table}.csv").read_bytes()
                self.edit(table, 0, field, value)
                with self.assertRaises(ImportValidationError):
                    import_bundle(self.directory)
                self.assertFalse(Category.objects.exists())
                (self.directory / f"{table}.csv").write_bytes(original)

    def test_broken_relation_is_rejected(self) -> None:
        self.edit("order_items", 0, "product_id", "999")
        with self.assertRaisesRegex(ImportValidationError, "unresolved product_id"):
            import_bundle(self.directory)
        self.assertFalse(Customer.objects.exists())

    def test_duplicate_primary_key_is_rejected(self) -> None:
        self.edit("products", 1, "product_id", "1")
        with self.assertRaisesRegex(ImportValidationError, "duplicate source key"):
            import_bundle(self.directory)

    def test_duplicate_headers_are_rejected(self) -> None:
        path = self.directory / "categories.csv"
        path.write_text("category_id,name,name\n1,A,A\n")
        with self.assertRaisesRegex(ImportValidationError, "columns"):
            import_bundle(self.directory)

    def test_missing_file_is_rejected(self) -> None:
        (self.directory / "promotions.csv").unlink()
        with self.assertRaises(ImportValidationError):
            import_bundle(self.directory)

    def test_multiple_active_promotions_are_rejected(self) -> None:
        self.edit("promotions", 1, "is_active", "1")
        with self.assertRaisesRegex(ImportValidationError, "multiple active"):
            import_bundle(self.directory)

    def test_late_database_failure_rolls_back_earlier_writes(self) -> None:
        with patch.object(
            Promotion.objects, "update_or_create", side_effect=IntegrityError("failure")
        ):
            with self.assertRaises(IntegrityError):
                import_bundle(self.directory)
        self.assertFalse(Category.objects.exists())
        self.assertFalse(Customer.objects.exists())
        self.assertFalse(OrderItem.objects.exists())

    def test_database_failure_restores_existing_values(self) -> None:
        import_bundle(self.directory)
        self.edit("products", 0, "price_brl", "12.00")
        with patch.object(
            Promotion.objects, "update_or_create", side_effect=IntegrityError("failure")
        ):
            with self.assertRaises(IntegrityError):
                import_bundle(self.directory)
        self.assertEqual(Product.objects.get(pk=1).price_brl, Decimal("1000.00"))
        self.assertTrue(Promotion.objects.get(pk=1).is_active)

    def test_active_campaign_can_be_switched_on_reimport(self) -> None:
        import_bundle(self.directory)
        self.edit("promotions", 0, "is_active", "0")
        self.edit("promotions", 1, "is_active", "1")
        import_bundle(self.directory)
        self.assertFalse(Promotion.objects.get(pk=1).is_active)
        self.assertTrue(Promotion.objects.get(pk=2).is_active)

    def test_original_filename_format_is_accepted(self) -> None:
        for path in self.directory.glob("*.csv"):
            path.rename(path.with_name(f"desafio_tecnico_ai_eng - {path.name}"))
        import_bundle(self.directory)
        self.assertEqual(Product.objects.count(), 5)

    def test_existing_rows_missing_from_bundle_are_retained(self) -> None:
        Category.objects.create(id=999, name="Local", description="Local category")
        import_bundle(self.directory)
        self.assertTrue(Category.objects.filter(pk=999).exists())

    def test_command_does_not_echo_personal_values(self) -> None:
        self.edit("customers", 0, "email", "invalid-private-contact")
        with self.assertRaises(CommandError) as caught:
            call_command("import_store_data", directory=self.directory, stdout=StringIO())
        self.assertNotIn("invalid-private-contact", str(caught.exception))
        self.assertIn("email", str(caught.exception))

    def test_database_error_output_is_sanitized(self) -> None:
        with patch(
            "apps.core.management.commands.import_store_data.import_bundle",
            side_effect=IntegrityError("private row content"),
        ):
            with self.assertRaises(CommandError) as caught:
                call_command("import_store_data", directory=self.directory, stdout=StringIO())
        self.assertNotIn("private row content", str(caught.exception))


class ModelGuaranteesTests(TestCase):
    """Check domain availability, database constraints and deletion protection."""

    @classmethod
    def setUpTestData(cls) -> None:
        import_bundle(FIXTURES)

    def test_availability_requires_active_status_and_stock(self) -> None:
        self.assertTrue(Product.objects.get(pk=1).is_available)
        for pk in (2, 3, 4):
            with self.subTest(product=pk):
                self.assertFalse(Product.objects.get(pk=pk).is_available)

    def test_database_rejects_invalid_values_even_without_full_clean(self) -> None:
        cases = [
            (Product, 1, {"price_brl": Decimal("-1")}),
            (Product, 1, {"stock_quantity": -1}),
            (Product, 1, {"status": "invalid"}),
            (Order, 1, {"total_brl": Decimal("-1")}),
            (Order, 1, {"payment_method": "invalid"}),
            (OrderItem, OrderItem.objects.first().pk, {"quantity": 0}),
            (Promotion, 1, {"discount_percent": Decimal("101")}),
            (Promotion, 2, {"is_active": True}),
        ]
        for model, pk, values in cases:
            with self.subTest(model=model.__name__, values=values):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    model.objects.filter(pk=pk).update(**values)

    def test_customer_with_orders_cannot_be_deleted_accidentally(self) -> None:
        with self.assertRaises(ProtectedError):
            Customer.objects.get(pk=1).delete()
