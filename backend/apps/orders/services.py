"""Authorized order lookup; caller identity never comes from model arguments."""

from datetime import date

from django.db.models import Prefetch
from django.utils import timezone

from apps.catalog.services import money
from apps.orders.models import Order, OrderItem


def get_order(order_id: int, *, customer_id: int | None, today: date | None = None) -> dict:
    """Look up an order only within a trusted customer scope.

    Missing and unauthorized orders deliberately return the same payload. No name,
    email, phone, address or customer list is returned to the language model.
    """
    if customer_id is None:
        return {"found": False, "reason": "customer_session_required"}
    order = (
        Order.objects.filter(pk=order_id, customer_id=customer_id)
        .prefetch_related(Prefetch("items", queryset=OrderItem.objects.select_related("product")))
        .first()
    )
    if order is None:
        return {"found": False, "reason": "not_found_in_customer_scope"}
    today = today or timezone.localdate()
    return {
        "found": True,
        "order_id": order.pk,
        "status": order.status,
        "order_date": order.order_date.isoformat(),
        "total_brl": money(order.total_brl),
        "payment_method": order.payment_method,
        "tracking_code": order.tracking_code,
        "estimated_delivery": order.estimated_delivery.isoformat()
        if order.estimated_delivery
        else None,
        "estimate_in_past": bool(order.estimated_delivery and order.estimated_delivery < today),
        "actual_delivery_date": None,
        "purchase_channel": None,
        "items": [
            {"product_id": item.product_id, "name": item.product.name, "quantity": item.quantity}
            for item in order.items.all()
        ],
        "source": "local_database_snapshot",
        "carrier_checked": False,
    }
