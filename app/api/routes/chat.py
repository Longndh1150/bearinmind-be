from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, status

from app.api.deps import require_active_user
from app.models.user import User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    MatchedUnit,
    MatchRationale,
    OpportunityAnalysisCard,
    TeamSuggestion,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with AI assistant (matching entrypoint)",
    description=(
        "US1 entrypoint. Accepts a user message and optional short history; "
        "returns assistant answer plus matched units and structured extraction (best-effort)."
    ),
)
async def chat(payload: ChatRequest, _: User = Depends(require_active_user)) -> ChatResponse:
    # Stubbed response shape for FE contract + OpenAPI stability.
    conv_id = payload.conversation_id or uuid4()
    return ChatResponse(
        conversation_id=UUID(str(conv_id)),
        answer="(stub) I understood your opportunity. Here are the best matching units.",
        extracted_opportunity=None,
        matched_units=[
            MatchedUnit(
                unit_id=uuid4(),
                unit_name="(stub) D365 Division",
                contact_name="(stub) Delivery Leader",
                contact_email="leader@rikkeisoft.com",
                fit_level="high",
                rationale=MatchRationale(
                    summary="(stub) Strong match based on D365 experience and Japan market delivery.",
                    evidence=["(stub) Case study: Retail D365 rollout", "(stub) Tech: D365 + Power Platform"],
                    confidence=0.82,
                ),
            )
        ],
        analysis_card=OpportunityAnalysisCard(
            title="(stub) Phân tích cơ hội mới",
            tags=[
                {"label": "Microsoft Dynamics 365", "tone": "purple"},
                {"label": "Nhật Bản", "tone": "teal"},
                {"label": "Cần Senior + Proposal", "tone": "amber"},
            ],
            footer_hint="(stub) Đã tìm thấy 2 đề xuất phù hợp — xem chi tiết bên dưới.",
        ),
        suggestions=[
            TeamSuggestion(
                name="(stub) Đơn vị DN1",
                match_level="High",
                tech_stack=[],
                case_studies=["D365 CRM", "D365 Business Central (BC)"],
                contact="ThangLB — Section Lead",
                suggestion_rank="Đề xuất 1",
                summary="(stub) Có kinh nghiệm triển khai D365 tại Nhật và APAC; đủ Senior để đảm nhận discovery + proposal.",
                contact_short_name="ThangLB",
                contact_role="SL",
                capability_tags=[
                    {"label": "3 Senior", "tone": "teal"},
                    {"label": "Có Senior chuyên sâu", "tone": "success"},
                ],
                variant="primary",
            ),
            TeamSuggestion(
                name="(stub) Đơn vị D5",
                match_level="Medium",
                tech_stack=[],
                case_studies=["D365 FO", "Integration hub"],
                contact="MinhLN — Delivery Lead",
                suggestion_rank="Đề xuất 2",
                summary="(stub) Quy mô lớn, nhiều dự án tích hợp; cần bổ sung Senior chuyên sâu D365 cho giai đoạn đầu.",
                contact_short_name="MinhLN",
                contact_role="DL",
                capability_tags=[
                    {"label": "10+ members", "tone": "gray"},
                    {"label": "Chưa có Senior chuyên sâu", "tone": "warning"},
                ],
                variant="secondary",
            ),
        ],
        suggested_actions=["save_opportunity_draft"],
    )

