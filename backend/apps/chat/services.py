"""Conversation use cases: ownership, persistence, idempotency and serialization."""

import logging
import uuid
from dataclasses import asdict

from django.db import DatabaseError, transaction

from apps.chat.agent import AgentReply, StoreAgent
from apps.chat.models import ChatTurn, Conversation, DemoAccess
from apps.chat.tools import AgentContext

logger = logging.getLogger(__name__)
MAX_TURNS = 25


class ConversationNotFound(Exception):
    """Hide the distinction between missing and other-session conversations."""


class ConversationConflict(Exception):
    """Represent a busy conversation, exhausted history or conflicting retry."""


def owned_conversations(*, access: DemoAccess, browser_session: uuid.UUID):
    """Apply the entire ownership scope before looking up any object."""
    return Conversation.objects.filter(
        owner_id=access.user_id,
        customer_id=access.customer_id,
        browser_session=browser_session,
    )


def get_conversation(*, access: DemoAccess, browser_session: uuid.UUID, identifier: uuid.UUID):
    """Use the same error for an unknown ID and an inaccessible ID."""
    conversation = (
        owned_conversations(access=access, browser_session=browser_session)
        .filter(pk=identifier)
        .first()
    )
    if conversation is None:
        raise ConversationNotFound
    return conversation


def submit_message(
    *,
    access: DemoAccess,
    browser_session: uuid.UUID,
    identifier: uuid.UUID,
    request_id: uuid.UUID,
    text: str,
) -> tuple[ChatTurn, bool]:
    """Serialize one conversation without holding a global lock or repeating retries.

    PostgreSQL NOWAIT rejects concurrent sends immediately. The transaction keeps
    the turn and bounded agent state consistent; a worker crash rolls both back.
    """
    try:
        with transaction.atomic():
            conversation = (
                owned_conversations(access=access, browser_session=browser_session)
                .select_for_update(nowait=True)
                .filter(pk=identifier)
                .first()
            )
            if conversation is None:
                raise ConversationNotFound
            previous = conversation.turns.filter(request_id=request_id).first()
            if previous:
                if previous.user_message != text:
                    raise ConversationConflict("request_id já utilizado com outra mensagem.")
                return previous, True
            if conversation.turns.count() >= MAX_TURNS:
                raise ConversationConflict("Limite de 25 envios atingido. Crie outra conversa.")
            agent = StoreAgent(context=AgentContext(customer_id=conversation.customer_id))
            agent.history = [dict(item) for item in conversation.agent_history]
            agent.product_references = {
                int(key): value for key, value in conversation.product_references.items()
            }
            try:
                # Roll back a failed agent-side database operation before persisting the error.
                with transaction.atomic():
                    reply = agent.reply(text)
            except DatabaseError:
                raise
            except Exception:
                logger.exception("Unexpected chat generation failure")
                reply = AgentReply("Não consegui concluir o atendimento agora.", "internal_error")
            turn = ChatTurn.objects.create(
                conversation=conversation, request_id=request_id, user_message=text, **asdict(reply)
            )
            if reply.status == "ok":
                conversation.agent_history = agent.history
                conversation.product_references = agent.product_references
            conversation.save(update_fields=["agent_history", "product_references", "updated_at"])
            return turn, False
    except DatabaseError as exc:
        if getattr(exc.__cause__, "sqlstate", None) == "55P03":
            raise ConversationConflict("Já existe um envio em andamento nesta conversa.") from None
        raise
