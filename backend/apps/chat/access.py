"""Issue demonstration credentials locally and resolve their customer binding."""

import hashlib
import secrets
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.chat.models import DemoAccess
from apps.customers.models import Customer

OWNER_SESSION_KEY = "chat_browser_session"


def token_digest(token: str) -> str:
    """Hash a random 256-bit token; never store its raw value."""
    return hashlib.sha256(token.encode()).hexdigest()


@transaction.atomic
def issue_demo_access(customer: Customer, *, hours: int = 24) -> tuple[DemoAccess, str]:
    """Create an unusable-password user and return the token exactly to the issuer."""
    if not 1 <= hours <= 168:
        raise ValueError("Expiry must be between 1 and 168 hours.")
    user = get_user_model()(username=f"demo_{uuid.uuid4().hex}")
    user.set_unusable_password()
    user.save()
    token = secrets.token_urlsafe(32)
    access = DemoAccess.objects.create(
        user=user,
        customer=customer,
        token_digest=token_digest(token),
        expires_at=timezone.now() + timedelta(hours=hours),
    )
    return access, token


def current_access(user) -> DemoAccess | None:
    """Recheck revocation/expiry on each HTTP request, not just at login."""
    if not user.is_authenticated or not user.is_active:
        return None
    return DemoAccess.objects.filter(
        user=user, is_active=True, expires_at__gt=timezone.now()
    ).first()
