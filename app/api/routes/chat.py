"""Chat routes — intent-aware, multi-flow."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.context_analyzer import analyze_context
from app.ai.agents.matching import run_matching
from app.ai.agents.title_generator import generate_title
from app.api.deps import get_session, require_active_user
from app.core.config import settings
from app.models.conversation import Conversation, ConversationMessage
from app.models.user import User
from app.schemas.chat import (
    ChatMessage,
    ChatMessageRequest,
    ChatResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationMessagePublic,
    ConversationSummary,
    MatchedUnit,
    MatchRationale,
    OpportunityAnalysisCard,
    TeamSuggestion,
)
from app.schemas.context import (
    ChatIntent,
    ConversationContext,
    DetectedLanguage,
    SessionMeta,
)
from app.services.update_capabilities_service import handle_update_capabilities

logger = logging.getLogger(__name__)

_NOW_FALLBACK = datetime.now(UTC)

router = APIRouter(prefix="/chat", tags=["chat"])


# ── helpers ────────────────────────────────────────────────────────────────────


def _build_analysis_card(
    extracted_title: str | None,
    suggestions: list[TeamSuggestion],
    language: DetectedLanguage = DetectedLanguage.vi,
) -> OpportunityAnalysisCard:
    tags: list[dict[str, str]] = []
    if extracted_title:
        tags.append({"label": extracted_title, "tone": "purple"})
    count = len(suggestions)
    if language == DetectedLanguage.vi:
        hint = f"Đã tìm thấy {count} đề xuất phù hợp." if count else "Chưa tìm thấy đơn vị phù hợp."
        title = "Phân tích cơ hội"
    elif language == DetectedLanguage.ja:
        hint = f"{count}件の適合ユニットが見つかりました。" if count else "適合するユニットが見つかりませんでした。"
        title = "機会分析"
    else:
        hint = f"Found {count} matching unit(s)." if count else "No matching units found."
        title = "Opportunity Analysis"
    return OpportunityAnalysisCard(title=title, tags=tags, footer_hint=hint)


def _stub_response(conv_id: UUID) -> ChatResponse:
    """Fallback when LLM is not configured (no LLM_API_KEY)."""
    return ChatResponse(
        conversation_id=conv_id,
        answer="(stub) Mô tả cơ hội của bạn (platform, thị trường, timeline) để AI tìm đơn vị phù hợp.",
        extracted_opportunity=None,
        matched_units=[
            MatchedUnit(
                unit_id="stub-d365",
                unit_name="(stub) D365 Division",
                contact_name="(stub) Delivery Leader",
                contact_email="leader@rikkeisoft.com",
                fit_level="high",
                rationale=MatchRationale(
                    summary="(stub) Strong match based on D365 experience.",
                    evidence=["(stub) Case study: Retail D365 rollout"],
                    confidence=0.82,
                ),
            )
        ],
        analysis_card=OpportunityAnalysisCard(
            title="(stub) Phân tích cơ hội mới",
            tags=[{"label": "stub mode — set LLM_API_KEY", "tone": "amber"}],
            footer_hint="Running in stub mode. Set LLM_API_KEY in .env to enable real matching.",
        ),
        suggestions=[
            TeamSuggestion(
                name="(stub) Đơn vị DN1",
                match_level="High",
                tech_stack=["D365", "Power Platform"],
                case_studies=["D365 CRM", "D365 Business Central"],
                contact="ThangLB — Section Lead",
                suggestion_rank="Đề xuất 1",
                summary="(stub) Có kinh nghiệm triển khai D365 tại Nhật và APAC.",
                contact_short_name="ThangLB",
                contact_role="SL",
                capability_tags=[{"label": "3 Senior", "tone": "teal"}],
                variant="primary",
            ),
        ],
        suggested_actions=["save_opportunity_draft"],
    )


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


def _load_session_meta(conv: Conversation) -> SessionMeta:
    """Deserialize session_meta from JSONB; return default if missing."""
    raw = getattr(conv, "session_meta", None)
    if raw and isinstance(raw, dict):
        return SessionMeta.model_validate(raw)
    return SessionMeta()


def _save_session_meta(conv: Conversation, meta: SessionMeta) -> None:
    conv.session_meta = meta.model_dump(mode="json")  # type: ignore[attr-defined]


def _build_history_for_context(
    messages: list[ConversationMessage],
) -> list[ChatMessage]:
    """Convert DB messages to ChatMessage list for context analyzer."""
    return [
        ChatMessage(role=m.role, content=m.content, created_at=m.created_at)  # type: ignore[arg-type]
        for m in messages[-8:]  # last 4 turns (user + assistant)
    ]


# ── intent-specific flow helpers ───────────────────────────────────────────────


def _handle_chitchat(
    ctx: ConversationContext,
    conv_id: UUID,
) -> ChatResponse:
    """Return a minimal response for greetings and off-topic messages."""
    if ctx.language == DetectedLanguage.vi:
        answer = "Xin chào! Tôi có thể giúp bạn tìm đơn vị phù hợp cho cơ hội kinh doanh. Hãy mô tả dự án của bạn nhé."
    elif ctx.language == DetectedLanguage.ja:
        answer = "こんにちは！プロジェクトの機会について説明していただければ、適切なユニットを見つけるお手伝いができます。"
    else:
        answer = "Hello! I can help you find matching divisions for a business opportunity. Please describe your project."
    return ChatResponse(
        conversation_id=conv_id,
        answer=answer,
        suggested_actions=[],
    )


def _handle_clarify(
    ctx: ConversationContext,
    conv_id: UUID,
) -> ChatResponse:
    """Return the clarification question the LLM suggested."""
    question = ctx.clarification_needed or (
        "Bạn có thể mô tả cụ thể hơn về cơ hội hoặc yêu cầu không?"
        if ctx.language == DetectedLanguage.vi
        else "Could you provide more details about the opportunity or request?"
    )
    return ChatResponse(
        conversation_id=conv_id,
        answer=question,
        suggested_actions=[],
    )


def _handle_unknown(conv_id: UUID, language: DetectedLanguage) -> ChatResponse:
    if language == DetectedLanguage.vi:
        answer = "Tôi chưa hiểu yêu cầu của bạn. Bạn có thể diễn đạt lại không? Ví dụ: mô tả dự án, yêu cầu công nghệ, thị trường mục tiêu."
    elif language == DetectedLanguage.ja:
        answer = "ご要望が理解できませんでした。プロジェクトや技術要件について詳しく教えていただけますか？"
    else:
        answer = "I didn't understand your request. Could you rephrase? For example: describe the project, required technology, or target market."
    return ChatResponse(
        conversation_id=conv_id,
        answer=answer,
        suggested_actions=[],
    )


def _handle_save_draft(
    ctx: ConversationContext,
    conv_id: UUID,
    session_meta: SessionMeta,
) -> ChatResponse:
    """Stub for US5 save_draft flow — to be implemented when OpportunityService is ready."""
    if session_meta.opportunity_draft_id:
        if ctx.language == DetectedLanguage.vi:
            answer = f"Cơ hội đã được lưu trước đó (ID: {session_meta.opportunity_draft_id}). Bạn có muốn cập nhật không?"
        else:
            answer = f"The opportunity was already saved (ID: {session_meta.opportunity_draft_id}). Do you want to update it?"
    else:
        if ctx.language == DetectedLanguage.vi:
            answer = "Tính năng lưu cơ hội đang được phát triển. Vui lòng thử lại sau."
        else:
            answer = "The save opportunity feature is coming soon. Please try again later."
    return ChatResponse(
        conversation_id=conv_id,
        answer=answer,
        suggested_actions=["push_to_crm"] if session_meta.opportunity_draft_id else [],
    )


def _handle_request_deal_form(
    ctx: ConversationContext,
    conv_id: UUID,
) -> ChatResponse:
    """Instruct FE to show the HubSpot deal form (US5 Case 2)."""
    if ctx.language == DetectedLanguage.vi:
        answer = "Tôi sẽ hiển thị form tạo deal HubSpot. Vui lòng điền thông tin và xác nhận."
    else:
        answer = "I'll show you the HubSpot deal creation form. Please fill in the details and confirm."
    return ChatResponse(
        conversation_id=conv_id,
        answer=answer,
        # FE reads this action to know it should open the deal form
        suggested_actions=["submit_deal_form"],
    )

async def _process_chat_turn(
    session: AsyncSession,
    conv: Conversation,
    message: str,
    *,
    is_new_conversation: bool,
) -> ChatResponse:
    """Persist user message, run intent routing + LLM flows, persist assistant + ui_payload."""
    conv_id: UUID = conv.id  # type: ignore[assignment]

    msgs_result = await session.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conv_id)
        .order_by(ConversationMessage.created_at)
    )
    prior_messages = list(msgs_result.scalars().all())
    history = _build_history_for_context(prior_messages)

    user_msg = ConversationMessage(
        conversation_id=conv_id,
        role="user",
        content=message,
    )
    session.add(user_msg)

    if not settings.llm_api_key:
        logger.debug("LLM_API_KEY not set — returning stub chat response")
        await session.commit()
        return _stub_response(conv_id)

    session_meta = _load_session_meta(conv)
    try:
        ctx: ConversationContext = analyze_context(
            message=message,
            history=history,
            session_meta=session_meta,
        )
    except Exception:
        logger.exception("Context analysis failed; falling back to stub")
        await session.commit()
        return _stub_response(conv_id)

    session_meta.language = ctx.language
    session_meta.last_intent = ctx.intent
    _save_session_meta(conv, session_meta)

    logger.info(
        "conv=%s intent=%s lang=%s confidence=%.2f",
        conv_id, ctx.intent.value, ctx.language.value, ctx.confidence,
    )

    answer_text: str
    response: ChatResponse

    intent = ctx.intent

    if intent == ChatIntent.find_units:
        try:
            extracted, matched_units, suggestions, answer_text = run_matching(
                message=message,
                language=ctx.language,
            )
        except Exception:
            logger.exception("Matching agent failed; falling back to stub")
            await session.commit()
            return _stub_response(conv_id)

        analysis_card = _build_analysis_card(extracted.title, suggestions, ctx.language)
        unit_count = len(matched_units)

        response = ChatResponse(
            conversation_id=conv_id,
            answer=answer_text,
            extracted_opportunity=extracted,
            matched_units=matched_units,
            analysis_card=analysis_card,
            suggestions=suggestions,
            suggested_actions=(
                ["save_opportunity_draft", "request_deal_form"] if unit_count else []
            ),
            context=ctx,
        )

    elif intent == ChatIntent.save_draft:
        response = _handle_save_draft(ctx, conv_id, session_meta)
        response = response.model_copy(update={"context": ctx})
        answer_text = response.answer

    elif intent == ChatIntent.request_deal_form:
        response = _handle_request_deal_form(ctx, conv_id)
        response = response.model_copy(update={"context": ctx})
        answer_text = response.answer

    elif intent == ChatIntent.update_capabilities:
        response = await handle_update_capabilities(ctx, conv_id, payload.message)
        response = response.model_copy(update={"context": ctx})
        answer_text = response.answer

    elif intent == ChatIntent.chitchat:
        response = _handle_chitchat(ctx, conv_id)
        response = response.model_copy(update={"context": ctx})
        answer_text = response.answer

    elif intent == ChatIntent.clarify:
        response = _handle_clarify(ctx, conv_id)
        response = response.model_copy(update={"context": ctx})
        answer_text = response.answer

    else:  # unknown
        response = _handle_unknown(conv_id, ctx.language)
        response = response.model_copy(update={"context": ctx})
        answer_text = response.answer

    ui_payload = response.model_dump(
        mode="json",
        exclude={"conversation_id"},
    )
    assistant_msg = ConversationMessage(
        conversation_id=conv_id,
        role="assistant",
        content=answer_text,
        ui_payload=ui_payload,
    )
    session.add(assistant_msg)

    if is_new_conversation and not getattr(conv, "title", None):
        title = generate_title(message)
        conv.title = title  # type: ignore[attr-defined]

    await session.commit()

    return response


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
    return await _process_chat_turn(
        session,
        conv,
        body.first_message,
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
                ui_payload=getattr(m, "ui_payload", None),
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
    return await _process_chat_turn(
        session,
        conv,
        payload.message,
        is_new_conversation=False,
    )
