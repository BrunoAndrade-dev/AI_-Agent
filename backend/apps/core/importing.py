"""Validate complete CSV bundles before applying atomic, repeatable upserts."""

import csv
import json
import re
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.catalog.models import Category, Product, Promotion
from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem

# CSV names are explicit; unrelated files and the policy PDF are not ingested.
TABLES = {
    "categories": (
        Category,
        {
            "category_id": "id",
            "name": "name",
            "description": "description",
        },
    ),
    "products": (
        Product,
        {
            "product_id": "id",
            "price_brl": "price_brl",
            "name": "name",
            "category_id": "category_id",
            "description": "description",
            "stock_quantity": "stock_quantity",
            "status": "status",
            "specs": "specs",
            "created_at": "created_at",
        },
    ),
    "customers": (
        Customer,
        {
            "customer_id": "id",
            "name": "name",
            "phone": "phone",
            "email": "email",
            "city": "city",
        },
    ),
    "orders": (
        Order,
        {
            "order_id": "id",
            "customer_id": "customer_id",
            "order_date": "order_date",
            "status": "status",
            "total_brl": "total_brl",
            "payment_method": "payment_method",
            "tracking_code": "tracking_code",
            "estimated_delivery": "estimated_delivery",
            "notes": "notes",
        },
    ),
    "order_items": (
        OrderItem,
        {
            "order_id": "order_id",
            "quantity": "quantity",
            "product_id": "product_id",
        },
    ),
    "promotions": (
        Promotion,
        {
            "promotion_id": "id",
            "product_id": "product_id",
            "discount_percent": "discount_percent",
            "description": "description",
            "is_active": "is_active",
        },
    ),
}

RELATIONS = {
    "products": {"category_id": "categories"},
    "orders": {"customer_id": "customers"},
    "order_items": {"order_id": "orders", "product_id": "products"},
    "promotions": {"product_id": "products"},
}


class ImportValidationError(ValueError):
    """Report safe source coordinates without echoing customer values."""


def convert_value(field: str, raw: str) -> Any:
    """Parse source values strictly, rejecting rounding and ambiguous coercions."""
    if field in {"tracking_code", "estimated_delivery"} and raw == "":
        return None
    if field in {
        "id",
        "category_id",
        "customer_id",
        "order_id",
        "product_id",
        "quantity",
        "stock_quantity",
    }:
        if not re.fullmatch(r"[0-9]+", raw):
            raise ValueError("expected unsigned integer")
        value = int(raw)
        if value == 0 and field != "stock_quantity":
            raise ValueError("expected positive integer")
        return value
    if field in {"price_brl", "total_brl", "discount_percent"}:
        value = Decimal(raw)
        if not value.is_finite() or value < 0 or value.as_tuple().exponent < -2:
            raise ValueError("expected nonnegative decimal with at most two decimal places")
        if field == "discount_percent" and not 0 < value <= 100:
            raise ValueError("expected discount between zero (exclusive) and 100")
        return value
    if field in {"created_at", "order_date", "estimated_delivery"}:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            raise ValueError("expected ISO date")
        return date.fromisoformat(raw)
    if field == "is_active":
        if raw not in {"0", "1"}:
            raise ValueError("expected 0 or 1")
        return raw == "1"
    if field == "specs":
        value = json.loads(raw)
        if not isinstance(value, dict) or not value:
            raise ValueError("expected nonempty JSON object")
        return value
    return raw


def read_table(directory: Path, table: str) -> list[dict[str, Any]]:
    """Read one strict CSV schema, accepting canonical or supplied filenames."""
    candidates = [directory / f"{table}.csv", directory / f"desafio_tecnico_ai_eng - {table}.csv"]
    found = [path for path in candidates if path.is_file()]
    if len(found) != 1:
        raise ImportValidationError(f"{table}: expected exactly one supported CSV filename.")
    model, mapping = TABLES[table]
    rows = []
    identities = set()
    with found[0].open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, strict=True)
        headers = reader.fieldnames or []
        if len(headers) != len(mapping) or set(headers) != set(mapping):
            raise ImportValidationError(f"{table}: missing, duplicate or unexpected columns.")
        for line, raw in enumerate(reader, start=2):
            if None in raw or any(value is None for value in raw.values()):
                raise ImportValidationError(f"{table}, row {line}: inconsistent column count.")
            values = {}
            for column, field in mapping.items():
                try:
                    values[field] = convert_value(field, raw[column])
                except (ValueError, InvalidOperation, OverflowError):
                    raise ImportValidationError(
                        f"{table}, row {line}, column {column}: invalid value."
                    ) from None
            # Foreign keys are checked against the complete bundle below. Avoid
            # DB lookups before import and never include ValidationError values in logs.
            excluded = [model._meta.get_field(field).name for field in RELATIONS.get(table, {})]
            try:
                model(**values).full_clean(
                    exclude=excluded, validate_unique=False, validate_constraints=False
                )
            except ValidationError as error:
                fields = ", ".join(error.message_dict)
                raise ImportValidationError(
                    f"{table}, row {line}: invalid fields ({fields})."
                ) from None
            identity = (
                (values["order_id"], values["product_id"])
                if table == "order_items"
                else values["id"]
            )
            if identity in identities:
                raise ImportValidationError(f"{table}, row {line}: duplicate source key.")
            identities.add(identity)
            rows.append(values)
    if not rows:
        raise ImportValidationError(f"{table}: empty input is not a complete bundle.")
    return rows


def load_bundle(directory: Path) -> dict[str, list[dict[str, Any]]]:
    """Validate all six sources and their internal references before any write."""
    bundle = {table: read_table(directory, table) for table in TABLES}
    ids = {
        table: {row["id"] for row in rows}
        for table, rows in bundle.items()
        if table != "order_items"
    }
    for table, relations in RELATIONS.items():
        for field, target in relations.items():
            for line, row in enumerate(bundle[table], start=2):
                if row[field] not in ids[target]:
                    raise ImportValidationError(f"{table}, row {line}: unresolved {field}.")
    active = Counter(row["product_id"] for row in bundle["promotions"] if row["is_active"])
    if any(count > 1 for count in active.values()):
        raise ImportValidationError("promotions: multiple active promotions for the same product.")
    orders_with_items = {row["order_id"] for row in bundle["order_items"]}
    if orders_with_items != ids["orders"]:
        raise ImportValidationError("orders: every supplied order must have at least one item.")
    return bundle


def source_warnings(bundle: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Summarize source anomalies without exposing personal information."""
    warnings = []
    emails = Counter(row["email"] for row in bundle["customers"])
    shared = sum(count > 1 for count in emails.values())
    if shared:
        warnings.append(f"Shared email groups: {shared}; customers kept separate.")
    products = {row["id"]: row for row in bundle["products"]}
    totals = Counter()
    for item in bundle["order_items"]:
        totals[item["order_id"]] += products[item["product_id"]]["price_brl"] * item["quantity"]
    differences = sum(totals[row["id"]] != row["total_brl"] for row in bundle["orders"])
    if differences:
        warnings.append(
            f"Historical totals differing from current catalog: {differences}; preserved."
        )
    restricted = sum(
        row["status"] != "active" and row["stock_quantity"] > 0 for row in products.values()
    )
    if restricted:
        warnings.append(f"Non-active products with positive stock: {restricted}; status preserved.")
    return warnings


def import_bundle(directory: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Upsert a complete bundle atomically, optionally rolling back a validation run.

    Missing database records are never deleted. Existing source keys are updated;
    order items use their (order, product) pair. Use separate databases for private
    and synthetic data: source IDs intentionally overlap.
    """
    bundle = load_bundle(directory)
    report = {"counts": {}, "warnings": source_warnings(bundle), "dry_run": dry_run}
    with transaction.atomic():
        # Deactivate imported promotions first to support changing the active campaign
        # without violating the partial unique constraint during an intermediate upsert.
        Promotion.objects.filter(pk__in=[row["id"] for row in bundle["promotions"]]).update(
            is_active=False
        )
        for table, (model, _) in TABLES.items():
            created = 0
            for row in bundle[table]:
                defaults = row.copy()
                if table == "order_items":
                    key = {field: defaults.pop(field) for field in ("order_id", "product_id")}
                else:
                    key = {"pk": defaults.pop("id")}
                _, is_new = model.objects.update_or_create(**key, defaults=defaults)
                created += is_new
            report["counts"][table] = {"created": created, "existing": len(bundle[table]) - created}
        if dry_run:
            transaction.set_rollback(True)
    return report
