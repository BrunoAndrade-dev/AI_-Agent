"""Order history with source totals preserved independently of current prices."""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Order(models.Model):
    """Represent a historical order without inventing receipt date or sales channel."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        CONFIRMED = "confirmed", "Confirmado"
        SHIPPED = "shipped", "Enviado"
        DELIVERED = "delivered", "Entregue"
        CANCELLED = "cancelled", "Cancelado"

    class PaymentMethod(models.TextChoices):
        PIX = "pix", "PIX"
        DEBIT = "debit", "Débito"
        BOLETO = "boleto", "Boleto"
        CREDIT_3X = "credit_3x", "Crédito 3x"
        CREDIT_6X = "credit_6x", "Crédito 6x"
        CREDIT_12X = "credit_12x", "Crédito 12x"

    id = models.PositiveIntegerField(primary_key=True)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="orders"
    )
    order_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, db_index=True)
    total_brl = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    tracking_code = models.CharField(max_length=80, null=True, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(total_brl__gte=0), name="order_total_nonnegative"),
            models.CheckConstraint(
                condition=Q(
                    status__in=["pending", "confirmed", "shipped", "delivered", "cancelled"]
                ),
                name="order_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    payment_method__in=[
                        "pix",
                        "debit",
                        "boleto",
                        "credit_3x",
                        "credit_6x",
                        "credit_12x",
                    ]
                ),
                name="order_payment_valid",
            ),
        ]


class OrderItem(models.Model):
    """Link an order to a product without fabricating historical unit prices."""

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="items")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="order_items"
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="order_product_unique"),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="order_item_quantity_positive"
            ),
        ]
