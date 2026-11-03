"""Provide a lightweight process liveness endpoint."""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers import HealthSerializer


class HealthView(APIView):
    """Report API liveness; database and model readiness are separate concerns."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses=HealthSerializer, tags=["Infrastructure"])
    def get(self, request: Request) -> Response:
        """Return a stable payload for API process health checks."""
        return Response({"status": "ok"})
