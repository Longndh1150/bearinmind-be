import logging
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai.tools.vector_search import VectorSearchResult
from app.schemas.chat import ChatMessage
from app.schemas.context import ChatIntent, ConversationContext, DetectedLanguage, SessionMeta
from app.schemas.llm import OpportunityExtract

logger = logging.getLogger(__name__)

class GraphState(TypedDict):
    # Chat interaction
    user_message: str
    history: list[ChatMessage]
    session_meta: SessionMeta | None
    user_preferred_language: DetectedLanguage | None
    
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
    logger.info("[Graph] Entering node_analyze_context")
    from app.ai.agents.context_analyzer import analyze_context_and_extract
    ctx, extracted = analyze_context_and_extract(
        message=state["user_message"],
        history=state.get("history", []),
        session_meta=state.get("session_meta"),
        user_preferred_language=state.get("user_preferred_language")
    )
    logger.info(f"[Graph] Exiting node_analyze_context: intent={ctx.intent.value}, lang={ctx.language.value}")
    
    return {
        "context": ctx, 
        "extracted_entities": extracted
    }

def route_intent(state: GraphState) -> str:
    ctx = state.get("context")
    if ctx and ctx.intent == ChatIntent.find_units:
        logger.info("[Graph] Routing to vector_search")
        return "vector_search"
    logger.info("[Graph] Routing to handle_other_intent")
    return "handle_other_intent"



def node_vector_search(state: GraphState) -> dict:
    logger.info("[Graph] Entering node_vector_search")
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
    logger.info(f"[Graph] Exiting node_vector_search with {len(results)} results")
    return {"search_results": results}

def node_summarize(state: GraphState) -> dict:
    logger.info("[Graph] Entering node_summarize")
    from app.ai.agents.matching import score_and_rank
    extracted = state["extracted_entities"]
    results = state["search_results"]
    ctx = state["context"]
    lang = ctx.language if ctx else DetectedLanguage.vi
    
    matched_units, matched_experts, suggestions, answer = score_and_rank(
        extracted, results, language=lang
    )
    logger.info("[Graph] Exiting node_summarize")
    
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
    workflow.add_node("vector_search", node_vector_search)
    workflow.add_node("summarize", node_summarize)
    workflow.add_node("handle_other_intent", node_handle_other_intent)
    
    workflow.add_edge(START, "analyze_context")
    workflow.add_conditional_edges("analyze_context", route_intent, {
        "vector_search": "vector_search",
        "handle_other_intent": "handle_other_intent"
    })
    workflow.add_edge("vector_search", "summarize")
    workflow.add_edge("summarize", END)
    workflow.add_edge("handle_other_intent", END)
    
    return workflow.compile()
