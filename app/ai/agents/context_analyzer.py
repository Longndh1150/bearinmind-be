"""Context Analyzer — LLM call 0 in every chat turn.

Classifies the user's intent, extracts relevant entities, and detects the language
in a SINGLE LLM CALL before any tools are activated.
This leverages ChatOpenRouter and tool-calling schemas matching the old separate steps.
"""

from __future__ import annotations

import logging
import time

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openrouter import ChatOpenRouter
from pydantic import BaseModel, Field

from app.ai.constants import LLM_CONTEXT_ANALYZER_MAX_TOKENS
from app.ai.prompts.context import classify_intent_prompt
from app.core.config import settings
from app.core.llm_tracking import LLMTrackingContext
from app.schemas.chat import ChatMessage
from app.schemas.context import (
    ChatIntent,
    ConversationContext,
    DetectedLanguage,
    SessionMeta,
)
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

class ToolGeneralChat(BaseModel):
    """Call this tool for greetings, complaints, small talk, or out-of-scope questions."""
    language: DetectedLanguage = Field(description="Detected language of the user message.")

# We bind these tools to the LLM. OpenRouter/Langchain will map the JSON response to one of these schemas.
_TOOLS = [ToolFindUnits, ToolSaveDraft, ToolSendNotification, ToolClarify, ToolGeneralChat]

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
        response = chain.invoke({
            "message": message,
            "history": history_msgs,
            "session_language": session_language,
            "last_intent": last_intent_val,
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
            # Phase 3 Skill: Authenticate/Request Missing info if required fields for Notification are not present
            notification_data = args.get("notification_extract", {})
            extracted_data = OpportunityExtract(**notification_data)
            target = args.get("target_unit")
            if not target and session_meta and getattr(session_meta, "last_target", None):
                target = session_meta.last_target
            
            # Simple check for missing information
            missing = []
            if not extracted_data.deadline:
                missing.append("thời gian / deadline")
            if not extracted_data.scope:
                missing.append("phạm vi yêu cầu (scope)")
            
            if missing:
                ctx.intent = ChatIntent.clarify
                missing_str = ", ".join(missing)
                tgt_name = target or "đơn vị"
                if detected_lang == DetectedLanguage.vi:
                    ctx.clarification_needed = f"Dạ vâng, để các đơn vị có thể hỗ trợ nhanh hơn, anh cho em xin thêm một số thông tin nhé: {missing_str}."
                else:
                    ctx.clarification_needed = f"Sure! To help the {tgt_name} assist you better, could you please provide: {missing_str}?"
                ctx.opportunity_hint = target
            else:
                ctx.intent = ChatIntent.send_notification
                ctx.opportunity_hint = target  # Reuse opportunity_hint to pass target down temporarily or update Context schema later.
                
        elif tool_name in ["ToolClarify", "clarify"]:
            ctx.intent = ChatIntent.clarify
            ctx.clarification_needed = args.get("clarification_needed", "Could not understand.")
            
        elif tool_name in ["ToolGeneralChat", "general_chat"]:
            ctx.intent = ChatIntent.unknown
            
        else:
            logger.warning(f"Unknown tool called: {tool_name}")
            return _fallback_context(message)

        return ctx, extracted_data

    except Exception as e:
        logger.exception(f"Context analysis LLM call failed: {e}; using fallback")
        return _fallback_context(message)