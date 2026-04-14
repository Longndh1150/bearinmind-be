from __future__ import annotations

import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, status

from app.ai.agents.matching import run_matching
from app.api.deps import require_active_user
from app.core.config import settings
from app.models.user import User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    MatchedUnit,
    MatchRationale,
    OpportunityAnalysisCard,
    TeamSuggestion,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

_FIT_TONE = {"High": "teal", "Medium": "amber"}


def _build_analysis_card(
    extracted_title: str | None,
    suggestions: list[TeamSuggestion],
) -> OpportunityAnalysisCard:
    tags: list[dict[str, str]] = []
    if extracted_title:
        tags.append({"label": extracted_title, "tone": "purple"})
    count = len(suggestions)
    hint = f"Đã tìm thấy {count} đề xuất phù hợp." if count else "Chưa tìm thấy đơn vị phù hợp."
    return OpportunityAnalysisCard(title="Phân tích cơ hội", tags=tags, footer_hint=hint)


def _stub_response(conv_id: UUID) -> ChatResponse:
    """Fallback when LLM is not configured (no LLM_API_KEY)."""
    return ChatResponse(
        conversation_id=conv_id,
        answer="(stub) Mô tả cơ hội của bạn (platform, thị trường, timeline) để AI tìm đơn vị phù hợp.",
        extracted_opportunity=None,
        matched_units=[
            MatchedUnit(
                unit_id=uuid4(),
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


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with AI assistant (US1 matching entrypoint)",
    description=(
        "Accepts a user message; runs entity extraction + vector search + LLM ranking. "
        "Returns assistant answer, extracted opportunity, matched units, "
        "analysis_card and suggestions for FE interactive components. "
        "Falls back to stub response when LLM_API_KEY is not set."
    ),
)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(require_active_user),
) -> ChatResponse:
    conv_id = payload.conversation_id or uuid4()

    # Skip real LLM call when key is not configured (dev/test without API key)
    if not settings.llm_api_key:
        logger.debug("LLM_API_KEY not set — returning stub chat response")
        return _stub_response(UUID(str(conv_id)))

    try:
        extracted, matched_units, suggestions = run_matching(payload.message)
    except Exception:
        logger.exception("Matching agent failed; falling back to stub")
        return _stub_response(UUID(str(conv_id)))

    unit_count = len(matched_units)
    answer = (
        f"Tôi đã phân tích cơ hội và tìm thấy {unit_count} đơn vị phù hợp."
        if unit_count
        else "Tôi chưa tìm thấy đơn vị phù hợp. Hãy cung cấp thêm thông tin về công nghệ và thị trường."
    )

    analysis_card = _build_analysis_card(extracted.title, suggestions)

    return ChatResponse(
        conversation_id=UUID(str(conv_id)),
        answer=answer,
        extracted_opportunity=extracted,
        matched_units=matched_units,
        analysis_card=analysis_card,
        suggestions=suggestions,
        suggested_actions=["save_opportunity_draft"] if unit_count else [],
    )
