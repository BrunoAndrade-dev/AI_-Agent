"""Read-only catalog tools with deterministic availability and BRL calculations."""

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Prefetch

from apps.catalog.models import Product, Promotion

CATEGORY_ALIASES = {
    "violao": "violoes",
    "ukulele": "ukuleles",
    "guitarra": "guitarras",
    "baixo": "baixos",
    "bateria": "baterias",
    "teclado": "teclados",
    "piano": "pianos",
}


def normalize(text: str) -> str:
    """Normalize accents and punctuation for small-catalog token matching."""
    plain = unicodedata.normalize("NFKD", text.casefold())
    return re.sub(
        r"[^a-z0-9]+", " ", "".join(c for c in plain if not unicodedata.combining(c))
    ).strip()


def money(value: Decimal) -> str:
    """Serialize BRL to exactly two decimal places using commercial rounding."""
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def product_payload(product: Product) -> dict:
    """Expose source facts and calculated quotes without stacking discounts."""
    promotions = list(product.promotions.all())
    active = next((promotion for promotion in promotions if promotion.is_active), None)
    price = product.price_brl
    offer = price * (1 - active.discount_percent / 100) if active else price
    return {
        "id": product.pk,
        "name": product.name,
        "category": product.category.name,
        "description": product.description,
        "specs": product.specs,
        "status": product.status,
        "stock_quantity": product.stock_quantity,
        "available": product.is_available,
        "currency": "BRL",
        "table_price": money(price),
        "current_price": money(offer),
        "pix_price": money(offer if active else price * Decimal("0.95")),
        "promotion": {
            "description": active.description,
            "discount_percent": str(active.discount_percent),
        }
        if active
        else None,
        "quote_only": True,
    }


def catalog_query():
    """Load source records and active promotions without per-product queries."""
    return (
        Product.objects.select_related("category")
        .prefetch_related(Prefetch("promotions", queryset=Promotion.objects.filter(is_active=True)))
        .order_by("price_brl", "id")
    )


def search_products(
    query: str = "",
    category: str = "",
    max_price: float | int | None = None,
    available_only: bool = True,
    limit: int = 8,
) -> dict:
    """Filter the small source catalog; budget refers to current non-PIX price.

    Results are capped but the total match count is explicit. Searching a named
    product with available_only=False distinguishes absence from unavailable stock.
    """
    products = catalog_query()
    if available_only:
        products = products.filter(status=Product.Status.ACTIVE, stock_quantity__gt=0)
    tokens = normalize(query).split()
    wanted_category = normalize(category)
    wanted_category = CATEGORY_ALIASES.get(wanted_category, wanted_category)
    matches = []
    for product in products:
        haystack = normalize(f"{product.name} {product.category.name} {product.description}")
        category_name = normalize(product.category.name)
        if wanted_category and wanted_category not in category_name:
            continue
        if not all(
            token in haystack or CATEGORY_ALIASES.get(token, token) in category_name
            for token in tokens
        ):
            continue
        payload = product_payload(product)
        if max_price is not None and Decimal(payload["current_price"]) > Decimal(str(max_price)):
            continue
        matches.append(payload)
    matches.sort(key=lambda item: (Decimal(item["current_price"]), item["id"]))
    return {"count": len(matches), "products": matches[:limit], "truncated": len(matches) > limit}


def get_product(product_id: int) -> dict:
    """Return one catalog record, including its unavailable status when applicable."""
    product = catalog_query().filter(pk=product_id).first()
    return {"found": bool(product), "product": product_payload(product) if product else None}
