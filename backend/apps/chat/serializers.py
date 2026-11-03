"""Explicit HTTP contracts; customer identity is never accepted from request bodies."""

from rest_framework import serializers

from apps.chat.models import ChatTurn, Conversation


class StrictSerializer(serializers.Serializer):
    """Reject unknown fields instead of silently ignoring identity injection."""

    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError(
                    {field: ["Campo não permitido."] for field in sorted(unknown)}
                )
        return super().to_internal_value(data)


class EmptyRequestSerializer(StrictSerializer):
    pass


class SessionLoginSerializer(StrictSerializer):
    access_token = serializers.CharField(
        min_length=20,
        max_length=128,
        write_only=True,
        help_text="Token emitido pelo comando local create_demo_access; nunca o ID do cliente.",
    )


class SessionStateSerializer(serializers.Serializer):
    authenticated = serializers.BooleanField()
    csrf_token = serializers.CharField()
    expires_at = serializers.DateTimeField(allow_null=True)


class MessageRequestSerializer(StrictSerializer):
    request_id = serializers.UUIDField(help_text="UUID novo por envio; reutilize apenas no retry.")
    text = serializers.CharField(min_length=1, max_length=2000, trim_whitespace=False)

    def validate_text(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("A mensagem não pode conter só espaços.")
        return value


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "created_at", "updated_at"]
        read_only_fields = fields


class SourceSerializer(serializers.Serializer):
    source = serializers.CharField()
    version = serializers.CharField()
    page = serializers.IntegerField(min_value=1)
    section = serializers.CharField()


class ChatTurnSerializer(serializers.ModelSerializer):
    sources = SourceSerializer(many=True, read_only=True)
    tools_used = serializers.ListField(child=serializers.CharField(), read_only=True)
    validation_errors = serializers.ListField(child=serializers.CharField(), read_only=True)

    class Meta:
        model = ChatTurn
        fields = [
            "id",
            "request_id",
            "user_message",
            "text",
            "status",
            "sources",
            "tools_used",
            "validation_errors",
            "created_at",
        ]
        read_only_fields = fields


class TurnResultSerializer(serializers.Serializer):
    turn = ChatTurnSerializer()
    replayed = serializers.BooleanField()


class TurnHistorySerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField()
    turns = ChatTurnSerializer(many=True)
    max_turns = serializers.IntegerField()


class ErrorDetailSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    fields = serializers.JSONField()


class ErrorSerializer(serializers.Serializer):
    error = ErrorDetailSerializer()
