"""Versioned policy source and page-aware retrieval chunks."""

from django.db import models


class PolicyDocument(models.Model):
    """Track the currently imported PDF by stable key, version and checksum."""

    key = models.SlugField(unique=True)
    source_name = models.CharField(max_length=255)
    version = models.CharField(max_length=40)
    sha256 = models.CharField(max_length=64)
    page_count = models.PositiveIntegerField()
    imported_at = models.DateTimeField(auto_now=True)


class PolicyChunk(models.Model):
    """Store a retrieval passage with its original PDF page and heading."""

    document = models.ForeignKey(PolicyDocument, on_delete=models.CASCADE, related_name="chunks")
    position = models.PositiveIntegerField()
    page = models.PositiveIntegerField()
    section = models.CharField(max_length=255)
    text = models.TextField()

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "position"], name="policy_chunk_position_unique"
            ),
            models.CheckConstraint(condition=models.Q(page__gt=0), name="policy_page_positive"),
        ]
