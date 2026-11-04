"""HTTP transport for demo sessions and the persistent store agent."""

import uuid

from django.contrib.auth import login, logout
from django.middleware.csrf import get_token
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    PolymorphicProxySerializer,
    extend_schema,
)
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.generics import ListCreateAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.chat.access import OWNER_SESSION_KEY, current_access, token_digest
from apps.chat.models import Conversation, DemoAccess
from apps.chat.serializers import (
    ChatTurnSerializer,
    ConversationSerializer,
    EmptyRequestSerializer,
    ErrorSerializer,
    MessageRequestSerializer,
    SessionLoginSerializer,
    SessionStateSerializer,
    TurnHistorySerializer,
    TurnResultSerializer,
)
from apps.chat.services import MAX_TURNS, get_conversation, owned_conversations, submit_message

CSRF = OpenApiParameter(
    "X-CSRFToken",
    str,
    OpenApiParameter.HEADER,
    required=True,
    description="Token obtido em GET /api/chat/session/; após login use o token renovado.",
)
ERRORS = {400: ErrorSerializer, 403: ErrorSerializer, 429: ErrorSerializer, 503: ErrorSerializer}


class PrivateResponseMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


class InvalidDemoToken(APIException):
    status_code = 401
    default_detail = "Acesso demonstrativo inválido ou expirado."
    default_code = "invalid_demo_token"


class DemoPermission(BasePermission):
    message = "Sessão demonstrativa ausente, revogada ou expirada."

    def has_permission(self, request, view) -> bool:
        access = current_access(request.user)
        if access is None or not request.session.get(OWNER_SESSION_KEY):
            return False
        request.demo_access = access
        return True


def browser_session(request) -> uuid.UUID:
    try:
        return uuid.UUID(request.session[OWNER_SESSION_KEY])
    except (KeyError, ValueError, TypeError):
        raise PermissionDenied("Sessão demonstrativa inválida.") from None


def session_state(request) -> dict:
    access = current_access(request.user)
    authenticated = access is not None and bool(request.session.get(OWNER_SESSION_KEY))
    return {
        "authenticated": authenticated,
        "csrf_token": get_token(request),
        "expires_at": access.expires_at if authenticated else None,
    }


class DemoSessionView(PrivateResponseMixin, APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chat_session"

    @extend_schema(
        responses={200: SessionStateSerializer, 429: ErrorSerializer, 503: ErrorSerializer},
        auth=[],
        tags=["Session"],
        description="Obtém CSRF e estado da sessão, sem revelar contatos ou identidade do cliente.",
    )
    def get(self, request):
        response = Response(session_state(request))
        response["Cache-Control"] = "no-store"
        return response

    @extend_schema(
        request=SessionLoginSerializer,
        responses={200: SessionStateSerializer, 401: ErrorSerializer, **ERRORS},
        parameters=[CSRF],
        auth=[],
        tags=["Session"],
        description="Troca token local por sessão HttpOnly. Rotaciona sessão e CSRF.",
    )
    def post(self, request):
        # DRF does not enforce CSRF for anonymous logins; enforce it explicitly.
        SessionAuthentication().enforce_csrf(request)
        serializer = SessionLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access = (
            DemoAccess.objects.select_related("user")
            .filter(
                token_digest=token_digest(serializer.validated_data["access_token"]),
                is_active=True,
                expires_at__gt=timezone.now(),
                user__is_active=True,
            )
            .first()
        )
        if access is None:
            raise InvalidDemoToken
        # Flush even when logging into the same user: each login gets a new browser scope.
        logout(request._request)
        login(request._request, access.user, backend="django.contrib.auth.backends.ModelBackend")
        request._user = access.user
        request.session[OWNER_SESSION_KEY] = str(uuid.uuid4())
        request.session.set_expiry(
            max(1, int((access.expires_at - timezone.now()).total_seconds()))
        )
        response = Response(session_state(request))
        response["Cache-Control"] = "no-store"
        return response

    @extend_schema(
        request=None,
        responses={204: None, 403: ErrorSerializer, 429: ErrorSerializer, 503: ErrorSerializer},
        parameters=[CSRF],
        auth=[],
        tags=["Session"],
        description="Encerra a sessão; conversas antigas não passam a outra sessão.",
    )
    def delete(self, request):
        SessionAuthentication().enforce_csrf(request)
        logout(request._request)
        return Response(status=204)


class ConversationPagination(PageNumberPagination):
    page_size = 20


class ConversationListView(PrivateResponseMixin, ListCreateAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated, DemoPermission]
    pagination_class = ConversationPagination
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chat_session"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Conversation.objects.none()
        return owned_conversations(
            access=self.request.demo_access, browser_session=browser_session(self.request)
        )

    @extend_schema(
        tags=["Conversations"], responses={200: ConversationSerializer(many=True), **ERRORS}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=EmptyRequestSerializer,
        responses={201: ConversationSerializer, **ERRORS},
        parameters=[CSRF],
        tags=["Conversations"],
        description="Cria conversa vinculada ao token e à sessão. Não aceita customer_id.",
    )
    def post(self, request, *args, **kwargs):
        serializer = EmptyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = Conversation.objects.create(
            owner=request.user,
            customer_id=request.demo_access.customer_id,
            browser_session=browser_session(request),
        )
        return Response(ConversationSerializer(conversation).data, status=201)


class ConversationMessagesView(PrivateResponseMixin, APIView):
    permission_classes = [IsAuthenticated, DemoPermission]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chat_send"

    @extend_schema(
        responses={
            200: TurnHistorySerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
            429: ErrorSerializer,
            503: ErrorSerializer,
        },
        tags=["Messages"],
        description="Histórico persistido, em ordem cronológica, limitado a 25 turnos.",
    )
    def get(self, request, conversation_id):
        conversation = get_conversation(
            access=request.demo_access,
            browser_session=browser_session(request),
            identifier=conversation_id,
        )
        return Response(
            {
                "conversation_id": conversation.id,
                "turns": ChatTurnSerializer(conversation.turns.all(), many=True).data,
                "max_turns": MAX_TURNS,
            }
        )

    @extend_schema(
        request=MessageRequestSerializer,
        responses={
            **ERRORS,
            201: OpenApiResponse(TurnResultSerializer, description="Novo turno concluído."),
            200: OpenApiResponse(
                TurnResultSerializer, description="Retry idempotente; sem nova geração."
            ),
            422: OpenApiResponse(
                TurnResultSerializer, description="Resposta não confirmada ou limite do agente."
            ),
            503: PolymorphicProxySerializer(
                component_name="ChatUnavailable",
                serializers=[TurnResultSerializer, ErrorSerializer],
                resource_type_field_name=None,
            ),
            404: ErrorSerializer,
            409: ErrorSerializer,
        },
        parameters=[CSRF],
        tags=["Messages"],
        examples=[
            OpenApiExample(
                "Consulta de catálogo",
                value={
                    "request_id": "14c832eb-7c36-49aa-98ca-0bf81ee316ea",
                    "text": "Quais violões disponíveis até R$ 1000?",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Resposta ilustrativa com a base sintética",
                value={
                    "turn": {
                        "id": "f26beb44-10ec-436e-b65b-86c4d282b1e3",
                        "request_id": "14c832eb-7c36-49aa-98ca-0bf81ee316ea",
                        "user_message": "Quais violões disponíveis até R$ 1000?",
                        "text": "Violão Exemplo Nylon: preço atual R$ 900,00.",
                        "status": "ok",
                        "sources": [],
                        "tools_used": ["search_products"],
                        "validation_errors": [],
                        "created_at": "2026-11-03T12:00:00Z",
                    },
                    "replayed": False,
                },
                response_only=True,
                status_codes=["201"],
            ),
            OpenApiExample(
                "Campo inválido",
                value={
                    "error": {
                        "code": "validation_error",
                        "message": "Revise os campos enviados.",
                        "fields": {"customer_id": ["Campo não permitido."]},
                    }
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
        description="Geração síncrona. Reutilize request_id somente para repetir o mesmo envio. "
        "Envios concorrentes na mesma conversa retornam 409. Falhas também são persistidas; "
        "para uma nova tentativa de geração, use outro request_id.",
    )
    def post(self, request, conversation_id):
        serializer = MessageRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        turn, replayed = submit_message(
            access=request.demo_access,
            browser_session=browser_session(request),
            identifier=conversation_id,
            request_id=serializer.validated_data["request_id"],
            text=serializer.validated_data["text"],
        )
        status_code = (
            (200 if replayed else 201)
            if turn.status == "ok"
            else (
                422
                if turn.status in {"unverified_response", "tool_limit", "context_limit"}
                else 503
            )
        )
        return Response(
            {"turn": ChatTurnSerializer(turn).data, "replayed": replayed}, status=status_code
        )
