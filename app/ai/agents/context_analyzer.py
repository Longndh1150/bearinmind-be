"""Context Analyzer — LLM call 0 in every chat turn.

Classifies the user's intent, extracts relevant entities, and detects the language
in a SINGLE LLM CALL before any tools are activated.
This leverages ChatOpenRouter and tool-calling schemas matching the old separate steps.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openrouter import ChatOpenRouter
from pydantic import BaseModel, Field

from app.ai.constants import LLM_CONTEXT_ANALYZER_MAX_TOKENS
from app.ai.prompts.context import classify_intent_prompt
from app.core.config import settings
from app.core.llm_tracking import LLMTrackingContext
from app.schemas.chat import ChatMessage
from app.schemas.context import ChatIntent, ConversationContext, DetectedLanguage, SessionMeta
from app.schemas.llm import OpportunityExtract

logger = logging.getLogger(__name__)

# Maximum number of recent turns to include in history_summary
_HISTORY_TURNS = 8

# Define our Pydantic classes for Tool Calling
class ToolFindUnits(BaseModel):
    """Call this tool when the user wants to find cross-sell or up-sell opportunities, match units, or search for experts."""
    language: DetectedLanguage = Field(description="Detected language of the user message.")
    opportunity_extract: OpportunityExtract = Field(
        description="Detailed requirements extracted from the user's query."
    )

class ToolSaveDraft(BaseModel):
    """Call this tool when the user intends to save current progress to CRM or proceed with a found opportunity."""
    language: DetectedLanguage = Field(description="Detected language of the user message.")
    save_draft_extract: OpportunityExtract = Field(
        description="Relevant entity data extracted for CRM creation."
    )

class ToolSendNotification(BaseModel):
    """Call this tool when the user intends to notify, connect, or request a unit/division for a project, or when providing missing info for a notification."""
    language: DetectedLanguage = Field(description="Detected language of the user message.")
    target_unit: str = Field(description="Name of the unit to notify, e.g. 'DN1'. MUST extract from conversation history if not specified in the current message. Use 'none' if unknown.")
    notification_extract: OpportunityExtract = Field(
        description="Relevant entity data extracted specifically for the notification. Merge with history."
    )

class ToolClarify(BaseModel):
    """Call this tool if the user's request is ambiguous or missing completely."""
    language: DetectedLanguage = Field(description="Detected language of the user message.")
    clarification_needed: str = Field(
        default="Missing context",
        description="A short explanation of what is missing or ambiguous."
    )

class ToolQnA(BaseModel):
    """Call this tool when the user asks a follow-up question about the matches or a technical concept."""
    language: DetectedLanguage = Field(description="Detected language of the user message.")

class ToolGeneralChat(BaseModel):
    """Call this tool for greetings, complaints, small talk, or out-of-scope questions."""
    language: DetectedLanguage = Field(description="Detected language of the user message.")

class ToolUpdateUnitCapabilities(BaseModel):
    """Use this tool when the user (a unit leader) wants to update, add, or record experts, skills, or tech stack for their unit.
    If the user has not provided enough information (e.g., skill name but no expert name), use 'ask_for_clarification' and provide the follow-up question in the same language.
    If all information is gathered, use 'execute_update'. Analyze the conversation history closely to determine the action."""
    language: DetectedLanguage = Field(description="Detected language of the user message.")
    action: Literal["ask_for_clarification", "execute_update"] = Field(description="If the user hasn't provided enough info, ask for clarification.")
    missing_info_question: str | None = Field(description="The actual question to ask if action is 'ask_for_clarification'. Reply in appropriate language.", default=None)
    added_tech_stack: list[str] | None = Field(description="List of new technical skills to add (if any).", default=None)
    added_experts: list[str] | None = Field(description="List of new expert names to add (if any).", default=None)

# We bind these tools to the LLM. OpenRouter/Langchain will map the JSON response to one of these schemas.
_TOOLS = [ToolFindUnits, ToolSaveDraft, ToolSendNotification, ToolClarify, ToolQnA, ToolGeneralChat, ToolUpdateUnitCapabilities]


def _looks_like_placeholder_expert(name: str) -> bool:
    raw = (name or "").strip().lower()
    if not raw:
        return True
    generic_markers = [
        "chuyên gia",
        "expert",
        "kỹ sư",
        "engineer",
        "nhân sự",
        "member",
        "automation test",
        "tester",
        "qa",
    ]
    return any(m in raw for m in generic_markers)


def _needs_capability_clarification(
    added_tech_stack: list[str] | None,
    added_experts: list[str] | None,
) -> bool:
    techs = [t for t in (added_tech_stack or []) if str(t).strip()]
    experts = [e for e in (added_experts or []) if str(e).strip()]
    if not experts:
        return True
    if any(_looks_like_placeholder_expert(e) for e in experts):
        return True
    # If user only provides a person name but no focus areas, keep asking to enrich capability quality.
    if not techs:
        return True
    return False


def _merge_opportunity_dicts(
    pending: dict | None,
    incoming: dict,
) -> dict:
    """Prefer non-empty incoming values; keep prior session values when new ones are null/empty."""
    base = dict(pending or {})
    for key, val in incoming.items():
        if val is None:
            continue
        if isinstance(val, list) and len(val) == 0:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        base[key] = val
    return base


def _enrich_scope_from_narrative(extracted: OpportunityExtract, message: str) -> None:
    """Infer scope from user text when the model left it empty."""
    if extracted.scope and extracted.scope.strip():
        return
    blob = " ".join(
        [
            message,
            extracted.description or "",
            extracted.notes or "",
            " ".join(extracted.requirements),
        ]
    ).lower()
    parts: list[str] = []
    if "d365" in blob or "dynamics 365" in blob or "dynamics365" in blob:
        parts.append("Microsoft Dynamics 365")
    if "bán lẻ" in blob or "retail" in blob:
        parts.append("mảng bán lẻ (Retail)")
    if re.search(r"\bcrm\b", blob):
        parts.append("CRM")
    if "business central" in blob or "bc" in blob.split():
        parts.append("Business Central")
    if parts:
        extracted.scope = " — ".join(parts)


def _format_opportunity_lines(extracted: OpportunityExtract, lang: DetectedLanguage) -> str:
    """Human-readable bullet list of everything we will echo back to the user."""
    lines: list[str] = []
    if extracted.title:
        lines.append(f"- Tiêu đề: {extracted.title}")
    if extracted.client:
        lines.append(f"- Khách hàng: {extracted.client}")
    if extracted.market:
        lines.append(f"- Thị trường: {extracted.market}")
    if extracted.tech_stack:
        lines.append(f"- Công nghệ: {', '.join(extracted.tech_stack)}")
    if extracted.scope:
        lines.append(f"- Phạm vi (scope): {extracted.scope}")
    if extracted.deadline:
        lines.append(f"- Thời hạn / mốc quan trọng: {extracted.deadline}")
    if extracted.customer_stage:
        lines.append(f"- Giai đoạn khách hàng: {extracted.customer_stage}")
    if extracted.requires_estimate_or_demo is not None:
        yn = "có" if extracted.requires_estimate_or_demo else "không"
        lines.append(f"- Cần estimate / demo: {yn}")
    if extracted.description:
        lines.append(f"- Mô tả: {extracted.description}")
    if extracted.notes:
        lines.append(f"- Ghi chú thêm: {extracted.notes}")
    if extracted.requirements:
        lines.append(f"- Yêu cầu / quy mô: {'; '.join(extracted.requirements)}")

    if lines:
        return "\n".join(lines)
    if lang == DetectedLanguage.vi:
        return "- (chưa tách được chi tiết — anh bổ sung giúp em nhé)"
    return "- (No structured details yet — please add more.)"


def _notification_missing_fields(extracted: OpportunityExtract) -> list[str]:
    """Fields required before sending a unit notification (aligned with US1 demo)."""
    missing: list[str] = []
    if not extracted.scope or not extracted.scope.strip():
        missing.append("phạm vi yêu cầu (scope / module)")
    if not extracted.deadline or not str(extracted.deadline).strip():
        missing.append("hạn chốt hoặc mốc thời gian quan trọng (ví dụ deadline nộp proposal)")
    if not extracted.customer_stage or not str(extracted.customer_stage).strip():
        missing.append("khách hàng đang ở giai đoạn nào")
    if extracted.requires_estimate_or_demo is None:
        missing.append("có cần estimate sơ bộ hoặc demo hệ thống không")
    return missing


def _llm_client() -> ChatOpenRouter:
    kwargs: dict = {"api_key": settings.llm_api_key or "no-key"}
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    return ChatOpenRouter(**kwargs, model=settings.llm_model_secondary, max_tokens=LLM_CONTEXT_ANALYZER_MAX_TOKENS, max_retries=1)

def _build_history_summary(history: list[ChatMessage]) -> list:
    """Convert last N turns to a list of LangChain messages."""
    if not history:
        return []
    recent = history[-_HISTORY_TURNS:]
    out = []
    for m in recent:
        if m.role == "user":
            out.append(HumanMessage(content=m.content[:2000]))
        elif m.role == "assistant":
            out.append(AIMessage(content=m.content[:2000]))
    return out

def _fallback_context(message: str) -> tuple[ConversationContext, OpportunityExtract | None]:
    """Return a safe fallback when the LLM call fails."""
    return ConversationContext(
        intent=ChatIntent.unknown,
        language=DetectedLanguage.vi,
        confidence=0.0,
        opportunity_hint=None,
        clarification_needed=None,
        raw_message=message,
    ), None

def analyze_context_and_extract(
    message: str,
    history: list[ChatMessage],
    session_meta: SessionMeta | None = None,
    user_preferred_language: DetectedLanguage | None = None,
) -> tuple[ConversationContext, OpportunityExtract | None]:
    """Unified Step 1 & 2: classify intent, extract entities, and detect language.

    Args:
        message: The current user message.
        history: Recent chat history.
        session_meta: Persisted session metadata.
        user_preferred_language: The user's preferred language.

    Returns:
        A tuple of (ConversationContext, extracted_entities_if_any)
    """
    if session_meta and session_meta.language:
        session_language = session_meta.language.value
    elif user_preferred_language:
        session_language = user_preferred_language.value
    else:
        session_language = DetectedLanguage.vi.value

    last_intent_val = session_meta.last_intent.value if session_meta and session_meta.last_intent else "none"

    history_msgs = _build_history_summary(history)

    client = _llm_client()
    
    # NEW PATTERN: Instead of generic JSON extraction, we force tool calling.
    llm_with_tools = client.bind_tools(_TOOLS, tool_choice="any")
    chain = classify_intent_prompt | llm_with_tools

    try:
        t0 = time.time()
        pending_raw = session_meta.pending_notification_extract if session_meta else None
        pending_opportunity = json.dumps(pending_raw, ensure_ascii=False) if pending_raw else "{}"

        response = chain.invoke({
            "message": message,
            "history": history_msgs,
            "session_language": session_language,
            "last_intent": last_intent_val,
            "pending_opportunity": pending_opportunity,
        })
        t1 = time.time()

        if hasattr(response, "usage_metadata"):
            LLMTrackingContext.log_call(
                operation_name="analyze_context_and_extract",
                elapsed_s=t1 - t0,
                usage=LLMTrackingContext._extract_usage(response),
                model=getattr(response, "response_metadata", {}).get("model_name", settings.llm_model_secondary),
            )
        
        # Parse the tool call mapping back to ConversationContext and Extracts
        if not response.tool_calls:
            # Fallback if the LLM didn't use a tool (rare with good models, but happens)
            logger.warning(f"LLM didn't return a tool call. Response content: {getattr(response, 'content', 'None')}")
            return _fallback_context(message)

        tool_call = response.tool_calls[0]
        tool_name = tool_call["name"]
        args = tool_call["args"]
        
        detected_lang_str = args.get("language", DetectedLanguage.vi)
        try:
            detected_lang = DetectedLanguage(detected_lang_str)
        except ValueError:
            detected_lang = DetectedLanguage.vi
            
        if detected_lang == DetectedLanguage.unknown:
            detected_lang = DetectedLanguage(session_language)
        
        # Default base context
        ctx = ConversationContext(
            intent=ChatIntent.unknown,
            language=detected_lang,
            confidence=0.9, # Tool calls are generally high confidence
            raw_message=message,
            clarification_needed=None,
            opportunity_hint=None
        )
        
        extracted_data = None
        
        if tool_name in ["ToolFindUnits", "find_units"]:
            ctx.intent = ChatIntent.find_units
            opportunity_extract_data = args.get("opportunity_extract", {})
            extracted_data = OpportunityExtract(**opportunity_extract_data)
            
        elif tool_name in ["ToolSaveDraft", "save_draft"]:
            ctx.intent = ChatIntent.save_draft
            save_draft_extract_data = args.get("save_draft_extract", {})
            extracted_data = OpportunityExtract(**save_draft_extract_data)
            
        elif tool_name in ["ToolSendNotification", "send_notification"]:
            ctx.notification_flow = True
            # Phase 3 Skill: Authenticate/Request Missing info if required fields for Notification are not present
            notification_data = args.get("notification_extract", {})
            merged_dict = _merge_opportunity_dicts(
                session_meta.pending_notification_extract if session_meta else None,
                notification_data,
            )
            extracted_data = OpportunityExtract(**merged_dict)
            _enrich_scope_from_narrative(extracted_data, message)

            target = args.get("target_unit")
            if not target and session_meta and getattr(session_meta, "last_target", None):
                target = session_meta.last_target

            missing = _notification_missing_fields(extracted_data)

            if missing:
                ctx.intent = ChatIntent.clarify
                missing_str = ", ".join(missing)
                tgt_name = (target or "đơn vị").strip() or "đơn vị"
                summary_block = _format_opportunity_lines(extracted_data, detected_lang)

                if detected_lang == DetectedLanguage.vi:
                    ctx.clarification_needed = (
                        f"Dạ vâng, em đã ghi nhận các thông tin anh cung cấp cho cơ hội này trong phiên làm việc "
                        f"(em sẽ giữ lại để anh không phải nhắc lại) như sau:\n"
                        f"{summary_block}\n\n"
                        f"Để bộ phận **{tgt_name}** chuẩn bị và hỗ trợ đúng ý anh, anh giúp em thêm: {missing_str}.\n"
                        f"Anh bổ sung hoặc chỉnh sửa giúp em nhé!"
                    )
                else:
                    ctx.clarification_needed = (
                        f"Thanks — here's what I have so far for this opportunity:\n"
                        f"{summary_block}\n\n"
                        f"To help **{tgt_name}** prepare, please also share: {missing_str}."
                    )
                ctx.opportunity_hint = target
            else:
                ctx.intent = ChatIntent.send_notification
                ctx.opportunity_hint = target  # Reuse opportunity_hint to pass target down temporarily or update Context schema later.
                
        elif tool_name in ["ToolClarify", "clarify"]:
            ctx.intent = ChatIntent.clarify
            ctx.clarification_needed = args.get("clarification_needed", "Could not understand.")
            
        elif tool_name in ["ToolUpdateUnitCapabilities", "update_unit_capabilities"]:
            ctx.intent = ChatIntent.update_capabilities
            action = args.get("action")
            added_tech_stack = args.get("added_tech_stack", [])
            added_experts = args.get("added_experts", [])
            must_clarify = _needs_capability_clarification(
                added_tech_stack=added_tech_stack,
                added_experts=added_experts,
            )

            if action == "ask_for_clarification" or must_clarify:
                ctx.clarification_needed = args.get("missing_info_question", "Could you provide more details?")
                if detected_lang == DetectedLanguage.vi and (
                    not ctx.clarification_needed
                    or ctx.clarification_needed == "Could you provide more details?"
                ):
                    ctx.clarification_needed = (
                        "Dạ em đã ghi nhận nhu cầu cập nhật năng lực ạ. "
                        "Anh cho em xin tên chuyên gia cụ thể và các mảng chuyên môn đi kèm "
                        "(ví dụ: Performance, Security...) để em lưu chính xác nhé?"
                    )
            else:
                payload = {
                    "added_tech_stack": added_tech_stack,
                    "added_experts": added_experts
                }
                ctx.opportunity_hint = json.dumps(payload)

        elif tool_name in ["ToolQnA", "qna"]:
            ctx.intent = ChatIntent.qna
            
        elif tool_name in ["ToolGeneralChat", "general_chat"]:
            ctx.intent = ChatIntent.unknown
            
        else:
            logger.warning(f"Unknown tool called: {tool_name}")
            return _fallback_context(message)

        return ctx, extracted_data

    except Exception as e:
        logger.exception(f"Context analysis LLM call failed: {e}; using fallback")
        return _fallback_context(message)