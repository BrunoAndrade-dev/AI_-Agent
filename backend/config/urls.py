"""Expose infrastructure routes and generated API documentation."""

from django.urls import path
from drf_spectacular.views import SpectacularAPIView

from apps.chat.views import ConversationListView, ConversationMessagesView, DemoSessionView
from apps.core.views import HealthView, SwaggerView

urlpatterns = [
    path("api/chat/session/", DemoSessionView.as_view(), name="chat-session"),
    path("api/chat/conversations/", ConversationListView.as_view(), name="chat-conversations"),
    path(
        "api/chat/conversations/<uuid:conversation_id>/messages/",
        ConversationMessagesView.as_view(),
        name="chat-messages",
    ),
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
