"""Define public infrastructure response contracts."""

from rest_framework import serializers


class HealthSerializer(serializers.Serializer):
    """Describe process liveness, without asserting dependency readiness."""

    status = serializers.ChoiceField(choices=["ok"])
