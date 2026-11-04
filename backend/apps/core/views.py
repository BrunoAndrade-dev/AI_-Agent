"""Provide a lightweight process liveness endpoint."""

from django.conf import settings
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularSwaggerView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers import HealthSerializer


class SwaggerView(SpectacularSwaggerView):
    """Preserve Swagger's auth handling while refreshing and deduplicating CSRF."""

    template_name_js = "core/swagger_ui.js"

    @extend_schema(exclude=True)
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.data["csrf_cookie_name"] = settings.CSRF_COOKIE_NAME
        response.data["settings"] = (
            "{ ...(" + response.data["settings"] + "), requestInterceptor: currentCsrfRequest }"
        )
        return response


class HealthView(APIView):
    """Report API liveness; database and model readiness are separate concerns."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses=HealthSerializer, tags=["Infrastructure"])
    def get(self, request: Request) -> Response:
        """Return a stable payload for API process health checks."""
        return Response({"status": "ok"})
