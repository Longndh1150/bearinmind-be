"""Chat Service - Business logic for chat coordination."""

import logging
import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.title_generator import generate_title
from app.ai.graph import GraphState, build_graph
from app.core.config import settings
from app.models.conversation import Conversation, ConversationMessage
from app.models.user import User
from app.schemas.chat import (
    ChatMessage,
    ChatResponse,
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
from app.schemas.llm import OpportunityExtract
from app.services.update_capabilities_service import handle_update_capabilities

logger = logging.getLogger(__name__)

# When user explicitly asks to open HubSpot deal form, we can skip the
# LLM "intent classification" step entirely.
_HUBSPOT_CMD_RE = re.compile(r"^\s*/hubspot\b", re.IGNORECASE)


class ChatService:
    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def _load_session_meta(conv: Conversation) -> SessionMeta:
        raw = getattr(conv, "session_meta", None)
        if raw and isinstance(raw, dict):
            return SessionMeta.model_validate(raw)
        return SessionMeta()

    @staticmethod
    def _save_session_meta(conv: Conversation, meta: SessionMeta) -> None:
        conv.session_meta = meta.model_dump(mode="json")  # type: ignore[attr-defined]

    @staticmethod
    def _build_history_for_context(
        messages: list[ConversationMessage],
    ) -> list[ChatMessage]:
        return [
            ChatMessage(role=m.role, content=m.content, created_at=m.created_at)  # type: ignore[arg-type]
            for m in messages[-8:]
        ]

    @staticmethod
    def _handle_chitchat(
        ctx: ConversationContext,
        conv_id: UUID,
    ) -> ChatResponse:
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

    @staticmethod
    def _handle_clarify(
        ctx: ConversationContext,
        conv_id: UUID,
    ) -> ChatResponse:
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

    @staticmethod
    def _handle_unknown(conv_id: UUID, language: DetectedLanguage) -> ChatResponse:
        if language == DetectedLanguage.vi:
            answer = "Gấu chưa hiểu yêu cầu của anh ạ. Anh có thể diễn đạt lại không? Ví dụ: mô tả dự án, yêu cầu công nghệ, thị trường mục tiêu."
        elif language == DetectedLanguage.ja:
            answer = "ご要望が理解できませんでした。プロジェクトや技術要件について詳しく教えていただけますか？"
        else:
            answer = "I didn't understand your request. Could you rephrase? For example: describe the project, required technology, or target market."
        return ChatResponse(
            conversation_id=conv_id,
            answer=answer,
            suggested_actions=[],
        )

    @staticmethod
    def _handle_save_draft(
        ctx: ConversationContext,
        conv_id: UUID,
        session_meta: SessionMeta,
    ) -> ChatResponse:
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

    @staticmethod
    async def _handle_send_notification(
        session: AsyncSession,
        ctx: ConversationContext,
        extracted: OpportunityExtract | None,
        conv_id: UUID,
        session_meta: SessionMeta,
        user: User,
    ) -> ChatResponse:
        from app.schemas.notification import (
            NotificationCreateOpportunityMatchUnitRequest,
            OpportunityMatchUnitNotificationDetails,
        )
        from app.services.notification_service import create_opportunity_match_unit_notification
        
        target_name = ctx.opportunity_hint or getattr(session_meta, "last_target", "") or ""
        matched_unit = None
        target_lower = target_name.lower().strip()
        for u in getattr(session_meta, "suggested_units", []):
            un_name = str(u.get("name", "")).lower()
            un_code = str(u.get("code", "")).lower()
            if target_lower in un_name or target_lower == un_code:
                matched_unit = u
                break
                
        if not matched_unit and target_name:
            from sqlalchemy import select
            from app.models.unit import Unit
            # Attempt to query from database directly
            unit_rs = await session.execute(
                select(Unit).where(
                    Unit.code.ilike(f"%{target_name}%") | Unit.name.ilike(f"%{target_name}%")
                )
            )
            db_unit = unit_rs.scalars().first()
            if db_unit:
                matched_unit = {
                    "id": str(db_unit.id),
                    "name": db_unit.name,
                    "code": db_unit.code,
                    "head_id": db_unit.contact_email
                }

        if not matched_unit:
            ans = f"Dạ, em không tìm thấy đơn vị '{target_name}' trong danh sách vừa gợi ý. Anh/chị vui lòng xác nhận lại nhé!" if ctx.language == DetectedLanguage.vi else f"Sorry, I couldn't find unit '{target_name}' in the recent suggestions. Could you confirm the unit?"
            return ChatResponse(conversation_id=conv_id, answer=ans, suggested_actions=[])
            
        # Try to resolve head_id which might be an email or placeholder
        unit_head_val = matched_unit.get("head_id")
        unit_head_id_uuid = None
        
        try:
            if unit_head_val:
                if "@" in unit_head_val:
                    from sqlalchemy import select
                    from app.models.user import User as DbUser
                    # query for user by email
                    head_rs = await session.execute(select(DbUser).where(DbUser.email == unit_head_val))
                    head_row = head_rs.scalar_one_or_none()
                    if head_row:
                        unit_head_id_uuid = head_row.id
                    else:
                        # Fallback to current user if head is not found in DB
                        unit_head_id_uuid = user.id
                else:
                    unit_head_id_uuid = UUID(unit_head_val)
        except Exception as e:
            logger.error(f"Error extracting unit_head user_id: {e}")
            unit_head_id_uuid = None

        if not unit_head_id_uuid:
            ans = f"Đơn vị {matched_unit.get('name')} hiện chưa có quản lý (đầu mối) để nhận thông báo ạ." if ctx.language == DetectedLanguage.vi else f"Unit {matched_unit.get('name')} currently does not have a designated head to receive notifications."
            return ChatResponse(conversation_id=conv_id, answer=ans, suggested_actions=[])
            
        details = OpportunityMatchUnitNotificationDetails(
            opportunity_name=extracted.title or "N/A" if extracted else "N/A",
            customer_group=extracted.market if extracted else None,
            deadline=None, # parsing str to date may be complex, ignoring or pass to bear_message
            required_tech=extracted.tech_stack if extracted else [],
            special_requirements=extracted.requirements[0] if extracted and extracted.requirements else None,
            next_steps="Estimate sơ bộ/Demo" if extracted and extracted.requires_estimate_or_demo else "Review",
            bear_message=extracted.notes if extracted else None,
            sales_contact_name=user.email.split("@")[0].capitalize() if user.email else "Sales",
            sales_contact_email=user.email,
        )
        
        req = NotificationCreateOpportunityMatchUnitRequest(
            recipient_user_id=unit_head_id_uuid,
            title=f"Opportunity match cho '{matched_unit.get('name')}' từ '{user.email}'",
            message=f"Có cơ hội mới, deadline/timeline dự kiến: {extracted.deadline if extracted and extracted.deadline else 'Chưa rõ'}, Scope: {extracted.scope if extracted and extracted.scope else 'Chưa rõ'}. Giai đoạn: {extracted.customer_stage if extracted and extracted.customer_stage else 'Chưa rõ'}.",
            details=details,
            unit_id=UUID(matched_unit["id"]),
            fit_level="medium"
        )
        
        try:
            await create_opportunity_match_unit_notification(session, req)
            ans = f"Dạ vâng, thông báo đã được gửi tới {matched_unit.get('name')} thành công ạ!" if ctx.language == DetectedLanguage.vi else f"Notification has been sent successfully to {matched_unit.get('name')}!"
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            ans = f"Đã xảy ra lỗi khi tạo thông báo tới {matched_unit.get('name')} ạ." if ctx.language == DetectedLanguage.vi else f"An error occurred while creating notification to {matched_unit.get('name')}."
            
        return ChatResponse(conversation_id=conv_id, answer=ans, suggested_actions=[])

    @staticmethod
    def _handle_request_deal_form(
        ctx: ConversationContext,
        conv_id: UUID,
    ) -> ChatResponse:
        if ctx.language == DetectedLanguage.vi:
            answer = "Tôi sẽ hiển thị form tạo deal HubSpot. Vui lòng điền thông tin và xác nhận."
        else:
            answer = "I'll show you the HubSpot deal creation form. Please fill in the details and confirm."
        return ChatResponse(
            conversation_id=conv_id,
            answer=answer,
            suggested_actions=["submit_deal_form"],
        )

    @staticmethod
    async def process_chat_turn(
        session: AsyncSession,
        conv: Conversation,
        message: str,
        user: User,
        *,
        is_new_conversation: bool,
    ) -> ChatResponse:
        conv_id: UUID = conv.id  # type: ignore[assignment]

        msgs_result = await session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv_id)
            .order_by(ConversationMessage.created_at)
        )
        prior_messages = list(msgs_result.scalars().all())
        history = ChatService._build_history_for_context(prior_messages)

        user_msg_id = uuid4()
        assistant_msg_id = uuid4()
        
        logger.info(f"Analyzing context for conv={conv_id}")

        user_msg = ConversationMessage(
            id=user_msg_id,
            conversation_id=conv_id,
            role="user",
            content=message,
            ui_payload={
                "message": message
            },
        )
        session.add(user_msg)

        response: ChatResponse | None = None

        if _HUBSPOT_CMD_RE.match(message or ""):
            session_meta = ChatService._load_session_meta(conv)
            ctx = ConversationContext(
                intent=ChatIntent.request_deal_form,
                language=session_meta.language,
                confidence=1.0,
                opportunity_hint=None,
                clarification_needed=None,
                raw_message=message,
            )
            session_meta.language = ctx.language
            session_meta.last_intent = ctx.intent
            ChatService._save_session_meta(conv, session_meta)

            response = ChatService._handle_request_deal_form(ctx, conv_id).model_copy(update={"context": ctx})
        elif not settings.llm_api_key:
            logger.debug("LLM_API_KEY not set — returning stub chat response")
            response = ChatService._stub_response(conv_id)
        else:
            session_meta = ChatService._load_session_meta(conv)
            try:
                # Add user preferred language to graph state mapping
                user_lang = None
                if user.preferred_language:
                    try:
                        user_lang = DetectedLanguage(user.preferred_language)
                    except ValueError:
                        pass
                
                graph = build_graph()
                
                initial_state: GraphState = {
                    "user_message": message,
                    "history": history,
                    "session_meta": session_meta,
                    "user_preferred_language": user_lang,
                    "context": None,
                    "extracted_entities": None,
                    "search_results": [],
                    "final_response": "",
                    "matched_units": [],
                    "matched_experts": [],
                    "suggestions": []
                }
                
                logger.info("Executing LangGraph for msg=%s", message[:20])
                start_graph = datetime.now(UTC)
                final_state = graph.invoke(initial_state)
                
                ctx: ConversationContext | None = final_state.get("context")
                if not ctx:
                    raise Exception("Graph execution failed to return a context.")
                    
                session_meta.language = ctx.language
                session_meta.last_intent = ctx.intent
                if ctx.opportunity_hint:
                    session_meta.last_target = ctx.opportunity_hint
                ChatService._save_session_meta(conv, session_meta)

                logger.info(
                    "[Graph Exec] conv=%s intent=%s lang=%s confidence=%.2f",
                    conv_id, ctx.intent.value, ctx.language.value, ctx.confidence,
                )

                intent = ctx.intent

                if intent == ChatIntent.find_units:
                    try:
                        extracted = final_state.get("extracted_entities")
                        matched_units = final_state.get("matched_units", [])
                        matched_experts = final_state.get("matched_experts", [])
                        suggestions = final_state.get("suggestions", [])
                        answer_text = final_state.get("final_response", "Match complete.")
                        
                        elapsed_matching = (datetime.now(UTC) - start_graph).total_seconds()
                        logger.info(f"conv={conv_id} graph_matching_time={elapsed_matching:.3f}s")
                        
                        analysis_card = ChatService._build_analysis_card(
                            extracted.title if extracted else None, 
                            suggestions, 
                            ctx.language
                        )
                        unit_count = len(matched_units)

                        response = ChatResponse(
                            conversation_id=conv_id,
                            answer=answer_text or "Đã nhận yêu cầu nhưng hệ thống chưa tổng hợp được câu trả lời.",
                            extracted_opportunity=extracted,
                            matched_units=matched_units,
                            matched_experts=matched_experts,
                            analysis_card=analysis_card,
                            suggestions=suggestions,
                            suggested_actions=(
                                ["save_opportunity_draft", "request_deal_form"] if unit_count else []
                            ),
                            context=ctx,
                        )
                        
                        # Phase 5: Cập nhật danh sách suggested_units vào session_meta
                        if matched_units:
                            try:
                                session_meta.suggested_units = []
                                for u in matched_units:
                                    session_meta.suggested_units.append({
                                        "id": str(getattr(u, "unit_id", "")),
                                        "name": getattr(u, "unit_name", ""),
                                        "code": getattr(u, "unit_name", ""), # Often code is name
                                        "head_id": getattr(u, "contact_email", None) # Map contact_email or similar
                                    })
                                ChatService._save_session_meta(conv, session_meta)
                            except Exception as emeta:
                                logger.warning(f"Could not save suggested_units: {emeta}")
                                
                    except Exception:
                        logger.exception("Matching agent failed; falling back to stub")
                        response = ChatService._stub_response(conv_id)

                elif intent == ChatIntent.send_notification:
                    logger.info("Executing send_notification intent")
                    extracted = final_state.get("extracted_entities")
                    response = await ChatService._handle_send_notification(
                        session=session,
                        ctx=ctx,
                        extracted=extracted,
                        conv_id=conv_id,
                        session_meta=session_meta,
                        user=user
                    )
                    response = response.model_copy(update={"context": ctx})

                elif intent == ChatIntent.save_draft:
                    response = ChatService._handle_save_draft(ctx, conv_id, session_meta)
                    response = response.model_copy(update={"context": ctx})

                elif intent == ChatIntent.request_deal_form:
                    response = ChatService._handle_request_deal_form(ctx, conv_id)
                    response = response.model_copy(update={"context": ctx})

                elif intent == ChatIntent.update_capabilities:
                    response = await handle_update_capabilities(ctx, conv_id, message)
                    response = response.model_copy(update={"context": ctx})

                elif intent == ChatIntent.chitchat:
                    response = ChatService._handle_chitchat(ctx, conv_id)
                    response = response.model_copy(update={"context": ctx})

                elif intent == ChatIntent.clarify:
                    response = ChatService._handle_clarify(ctx, conv_id)
                    response = response.model_copy(update={"context": ctx})

                else:
                    response = ChatService._handle_unknown(conv_id, ctx.language)
                    response = response.model_copy(update={"context": ctx})

            except Exception:
                logger.exception("Context analysis failed; falling back to stub")
                response = ChatService._stub_response(conv_id)

        if response is None:
            response = ChatService._stub_response(conv_id)

        response.message_id = assistant_msg_id
        response.user_message_id = user_msg_id

        ui_payload = response.model_dump(
            mode="json",
            exclude={"conversation_id", "message_id", "user_message_id"},
        )
        assistant_msg = ConversationMessage(
            id=assistant_msg_id,
            conversation_id=conv_id,
            role="assistant",
            content=response.answer,
            ui_payload=ui_payload,
        )
        session.add(assistant_msg)

        if is_new_conversation and not getattr(conv, "title", None):
            title = generate_title(message)
            conv.title = title  # type: ignore[attr-defined]

        await session.commit()

        return response
