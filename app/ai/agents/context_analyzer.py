"""Context Analyzer — LLM call 0 in every chat turn.

Classifies the user's intent, extracts relevant entities, and detects the language
in a SINGLE LLM CALL before any tools are activated.
This leverages ChatOpenRouter and tool-calling schemas matching the old separate steps.
"""

from __future__ import annotations

import logging
import time
from typing import Literal

from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel, Field

from app.ai.prompts.context import classify_intent_prompt
from app.ai.constants import LLM_CONTEXT_ANALYZER_MAX_TOKENS
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
_HISTORY_TURNS = 4

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
_TOOLS = [ToolFindUnits, ToolSaveDraft, ToolClarify, ToolGeneralChat]

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
            out.append(HumanMessage(content=m.content[:300]))
        elif m.role == "assistant":
            out.append(AIMessage(content=m.content[:300]))
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

    history_msgs = _build_history_summary(history)

    client = _llm_client()
    
    # NEW PATTERN: Instead of generic JSON extraction, we force tool calling.
    llm_with_tools = client.bind_tools(_TOOLS)
    chain = classify_intent_prompt | llm_with_tools

    try:
        t0 = time.time()
        response = chain.invoke({
            "message": message,
            "history": history_msgs,
            "session_language": session_language,
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
            logger.warning("LLM didn't return a tool call. Using fallback.")
            return _fallback_context(message)

        tool_call = response.tool_calls[0]
        tool_name = tool_call["name"]
        args = tool_call["args"]
        
        # Default base context
        ctx = ConversationContext(
            intent=ChatIntent.unknown,
            language=DetectedLanguage(args.get("language", DetectedLanguage.vi)), # type: ignore
            confidence=0.9, # Tool calls are generally high confidence
            raw_message=message,
            clarification_needed=None,
            opportunity_hint=None
        )
        
        extracted_data = None
        
        if tool_name == "ToolFindUnits":
            ctx.intent = ChatIntent.find_units
            opportunity_extract_data = args.get("opportunity_extract", {})
            extracted_data = OpportunityExtract(**opportunity_extract_data)
            
        elif tool_name == "ToolSaveDraft":
            ctx.intent = ChatIntent.save_draft
            save_draft_extract_data = args.get("save_draft_extract", {})
            extracted_data = OpportunityExtract(**save_draft_extract_data)
            
        elif tool_name == "ToolClarify":
            ctx.intent = ChatIntent.clarify
            ctx.clarification_needed = args.get("clarification_needed", "Could not understand.")
            
        elif tool_name == "ToolGeneralChat":
            ctx.intent = ChatIntent.unknown
            
        else:
            logger.warning(f"Unknown tool called: {tool_name}")
            return _fallback_context(message)

        return ctx, extracted_data

    except Exception:
        logger.exception("Context analysis LLM call failed; using fallback")
        return _fallback_context(message)