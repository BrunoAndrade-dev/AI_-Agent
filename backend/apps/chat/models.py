"""Persistent browser conversations and locally issued demonstration access."""

import uuid

from django.conf import settings
from django.db import models


class DemoAccess(models.Model):
    """Bind a high-entropy access token hash to one local user/customer."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT)
    token_digest = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class Conversation(models.Model):
    """Keep agent state under both authenticated user and browser-session ownership."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    browser_session = models.UUIDField(db_index=True)
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT)
    agent_history = models.JSONField(default=list)
    product_references = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]


class ChatTurn(models.Model):
    """Persist each submitted message and effective reply, including failures."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="turns")
    request_id = models.UUIDField()
    user_message = models.TextField()
    text = models.TextField()
    status = models.CharField(max_length=40)
    sources = models.JSONField(default=list)
    tools_used = models.JSONField(default=list)
    validation_errors = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "request_id"], name="chat_turn_request_unique"
            ),
        ]
