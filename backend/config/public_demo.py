"""Isolated HTTPS demo settings; never changes the local development server."""

from .settings import *  # noqa: F403

DEBUG = False
SESSION_COOKIE_NAME = "emporio_public_demo_session"
CSRF_COOKIE_NAME = "emporio_public_demo_csrf"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Only cloudflared reaches this container; it overwrites the forwarded scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
# A short, host-only policy suits a temporary demo hostname.
SECURE_HSTS_SECONDS = 3600
