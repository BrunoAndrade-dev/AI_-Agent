"""Catalog records imported from operational sources."""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Category(models.Model):
    """Group products using the original category identifier."""

    id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=120)
    description = models.TextField()


class Product(models.Model):
    """Preserve source facts; stock alone does not establish availability."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Ativo"
        DISCONTINUED = "discontinued", "Descontinuado"
        COMING_SOON = "coming_soon", "Em breve"

    id = models.PositiveIntegerField(primary_key=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField()
    price_brl = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    stock_quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, db_index=True)
    specs = models.JSONField(default=dict)
    created_at = models.DateField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(price_brl__gte=0), name="product_price_nonnegative"),
            models.CheckConstraint(
                condition=Q(status__in=["active", "discontinued", "coming_soon"]),
                name="product_status_valid",
            ),
        ]

    @property
    def is_available(self) -> bool:
        """Return whether the current status and stock permit an offer."""
        return self.status == self.Status.ACTIVE and self.stock_quantity > 0


class Promotion(models.Model):
    """Describe a source promotion without inferring dates from its campaign name."""

    id = models.PositiveIntegerField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="promotions")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2)
    description = models.CharField(max_length=255)
    is_active = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(discount_percent__gt=0, discount_percent__lte=100),
                name="promotion_discount_valid",
            ),
            models.UniqueConstraint(
                fields=["product"],
                condition=Q(is_active=True),
                name="one_active_promotion_per_product",
            ),
        ]
