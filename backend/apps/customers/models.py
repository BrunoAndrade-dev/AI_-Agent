"""Customer source records; identity verification belongs to the access layer."""

from django.db import models


class Customer(models.Model):
    """Keep contacts private and permit shared email addresses from the source."""

    id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=40)
    email = models.EmailField(max_length=254)
    city = models.CharField(max_length=120)
