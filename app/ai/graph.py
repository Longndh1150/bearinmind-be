import logging
from typing import TypedDict, Annotated, Literal
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, START, END

from app.schemas.llm import OpportunityExtract
from app.ai.tools.vector_search import VectorSearchResult
from app.schemas.context import ChatIntent, DetectedLanguage, ConversationContext, SessionMeta
from app.schemas.chat import ChatMessage

logger = logging.getLogger(__name__)

class GraphState(TypedDict):
    # Chat interaction
    user_message: str
    history: list[ChatMessage]
    session_meta: SessionMeta | None
    
    # Context
    context: ConversationContext | None
    
    # Extraction & Search
    extracted_entities: OpportunityExtract | None
    search_results: list[VectorSearchResult]
    
    # Results
    final_response: str
    matched_units: list
    matched_experts: list
    suggestions: list

def node_analyze_context(state: GraphState) -> dict:
    from app.ai.agents.context_analyzer import analyze_context
    ctx = analyze_context(
        message=state["user_message"],
        history=state.get("history", []),
        session_meta=state.get("session_meta")
    )
    return {"context": ctx}

def route_intent(state: GraphState) -> str:
    ctx = state.get("context")
    if ctx and ctx.intent == ChatIntent.find_units:
        return "extract_entities"
    return "handle_other_intent"

def node_extract_entities(state: GraphState) -> dict:
    from app.ai.agents.matching import extract_entities
    ctx = state["context"]
    lang = ctx.language if ctx else DetectedLanguage.vi
    extracted = extract_entities(state["user_message"], language=lang)
    return {"extracted_entities": extracted}

def node_vector_search(state: GraphState) -> dict:
    from app.ai.tools.vector_search import search_units
    extracted = state.get("extracted_entities")
    message = state["user_message"]
    
    if extracted:
        query = " ".join(extracted.tech_stack + extracted.requirements)
        if not query.strip():
            query = message[:500]
    else:
        query = message[:500]
        
    results = search_units(query, top_k=3)
    return {"search_results": results}

def node_summarize(state: GraphState) -> dict:
    from app.ai.agents.matching import score_and_rank, _build_answer
    extracted = state["extracted_entities"]
    results = state["search_results"]
    ctx = state["context"]
    lang = ctx.language if ctx else DetectedLanguage.vi
    
    matched_units, matched_experts, suggestions = score_and_rank(
        extracted, results, language=lang
    )
    answer = _build_answer(state["user_message"], extracted, matched_units, matched_experts, language=lang)
    
    return {
        "final_response": answer,
        "matched_units": matched_units,
        "matched_experts": matched_experts,
        "suggestions": suggestions
    }

def node_handle_other_intent(state: GraphState) -> dict:
    # For intents other than find_units, we just return so the router can handle it.
    return {}

def build_graph():
    workflow = StateGraph(GraphState)
    
    workflow.add_node("analyze_context", node_analyze_context)
    workflow.add_node("extract_entities", node_extract_entities)
    workflow.add_node("vector_search", node_vector_search)
    workflow.add_node("summarize", node_summarize)
    workflow.add_node("handle_other_intent", node_handle_other_intent)
    
    workflow.add_edge(START, "analyze_context")
    workflow.add_conditional_edges("analyze_context", route_intent, {
        "extract_entities": "extract_entities",
        "handle_other_intent": "handle_other_intent"
    })
    workflow.add_edge("extract_entities", "vector_search")
    workflow.add_edge("vector_search", "summarize")
    workflow.add_edge("summarize", END)
    workflow.add_edge("handle_other_intent", END)
    
    return workflow.compile()
