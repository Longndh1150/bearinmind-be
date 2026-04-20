"""Chat routes — intent-aware, multi-flow."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_active_user
from app.models.conversation import Conversation, ConversationMessage
from app.models.user import User
from app.schemas.chat import (
    ChatMessageRequest,
    ChatResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationMessagePublic,
    ConversationSummary,
)
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# ── helpers ────────────────────────────────────────────────────────────────────

async def _get_conv_or_404(
    conversation_id: UUID,
    user_id: UUID,
    session: AsyncSession,
) -> Conversation:
    conv = await session.get(Conversation, conversation_id)
    if not conv or conv.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv

def _to_summary(conv: Conversation, messages: list[ConversationMessage]) -> ConversationSummary:
    last_user_msg = next(
        (m.content for m in reversed(messages) if m.role == "user"),
        None,
    )
    preview = last_user_msg[:200] if last_user_msg else None
    return ConversationSummary(
        id=conv.id,
        title=conv.title if hasattr(conv, "title") else None,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        last_message_preview=preview,
    )

# ── Conversation & message API ─────────────────────────────────────────────────


@router.get(
    "",
    response_model=list[ConversationSummary],
    summary="List conversations",
    description="Returns conversations for the current user, most recently updated first.",
)
async def list_conversations(
    current_user: User = Depends(require_active_user),
    session: AsyncSession = Depends(get_session),
) -> list[ConversationSummary]:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    convs = result.scalars().all()

    summaries: list[ConversationSummary] = []
    for conv in convs:
        msgs_result = await session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv.id)
            .order_by(ConversationMessage.created_at)
        )
        msgs = list(msgs_result.scalars().all())
        summaries.append(_to_summary(conv, msgs))
    return summaries


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Create conversation and send first message",
    description=(
        "Creates a new conversation, processes `first_message` through the same "
        "intent-aware pipeline as POST /chat/{conversation_id}, persists messages, "
        "and generates a conversation title from the first message (secondary LLM). "
        "Returns `ChatResponse` with `conversation_id` for subsequent turns."
    ),
)
async def create_conversation_and_chat(
    body: ConversationCreate,
    current_user: User = Depends(require_active_user),
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    new_id = uuid4()
    conv = Conversation(id=new_id, user_id=current_user.id)
    session.add(conv)
    await session.flush()
    return await ChatService.process_chat_turn(
        session,
        conv,
        body.first_message,
        user=current_user,
        is_new_conversation=True,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
    summary="Get messages for a conversation",
    description="Returns metadata and full message history (including assistant ui_payload). Owner only.",
)
async def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(require_active_user),
    session: AsyncSession = Depends(get_session),
) -> ConversationDetail:
    conv = await _get_conv_or_404(conversation_id, current_user.id, session)

    msgs_result = await session.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conv.id)
        .order_by(ConversationMessage.created_at)
    )
    msgs = list(msgs_result.scalars().all())

    return ConversationDetail(
        id=conv.id,
        title=getattr(conv, "title", None),
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[
            ConversationMessagePublic(
                id=m.id,
                role=m.role,  # type: ignore[arg-type]
                content=m.content,
                created_at=m.created_at,
                ui_payload=getattr(m, "ui_payload", None) or {},
            )
            for m in msgs
        ],
    )


@router.post(
    "/{conversation_id}",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a message in an existing conversation",
    description=(
        "Intent-aware chat: same pipeline as POST /chat but for an existing "
        "`conversation_id` (path). Persists user + assistant turns and session context."
    ),
)
async def send_message_in_conversation(
    conversation_id: UUID,
    payload: ChatMessageRequest,
    current_user: User = Depends(require_active_user),
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    conv = await _get_conv_or_404(conversation_id, current_user.id, session)
    return await ChatService.process_chat_turn(
        session,
        conv,
        payload.message,
        user=current_user,
        is_new_conversation=False,
    )
