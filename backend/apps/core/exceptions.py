"""Provide one documented, sanitized error envelope for the HTTP API."""

import logging

from django.db import DatabaseError
from rest_framework.exceptions import APIException, NotFound
from rest_framework.views import exception_handler

from apps.chat.services import ConversationConflict, ConversationNotFound

logger = logging.getLogger(__name__)


class Conflict(APIException):
    status_code = 409
    default_code = "conflict"


class ServiceUnavailable(APIException):
    status_code = 503
    default_code = "service_unavailable"


def api_exception_handler(exc, context):
    """Preserve DRF status/headers while making validation errors predictable."""
    if isinstance(exc, ConversationNotFound):
        exc = NotFound("Conversa não encontrada nesta sessão.")
    elif isinstance(exc, ConversationConflict):
        exc = Conflict(str(exc))
    elif isinstance(exc, DatabaseError):
        logger.exception("Database unavailable during API request")
        exc = ServiceUnavailable("Não consegui consultar os dados agora.")
    response = exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    detail = data.get("detail") if isinstance(data, dict) else None
    response.data = {
        "error": {
            "code": str(getattr(detail, "code", "validation_error")),
            "message": str(detail) if detail else "Revise os campos enviados.",
            "fields": {} if detail else data,
        }
    }
    return response
