from typing import TypedDict, Annotated, Literal
import operator

from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, START, END

from app.schemas.llm import OpportunityExtract
from app.ai.tools.vector_search import VectorSearchResult
from app.schemas.context import ChatIntent, DetectedLanguage

class GraphState(TypedDict):
    # Chat interaction
    messages: list[BaseMessage]
    user_message: str
    
    # Context
    preferred_language: str
    detected_language: DetectedLanguage
    intent: ChatIntent
    
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
    from app.schemas.chat import ChatMessage
    
    # We map BaseMessages to the old ChatMessage structure required by legacy analyzer
    # or just use the newest logic.
    ctx = analyze_context(state["user_message"], [])  # simplified for now
    
    return {
        "intent": ctx.intent,
        "detected_language": ctx.language
    }

def route_intent(state: GraphState) -> str:
    if state.get("intent") == ChatIntent.find_units:
        return "extract_entities"
    return "handle_other_intent"

def node_extract_entities(state: GraphState) -> dict:
    from app.ai.agents.matching import extract_entities
    lang = state.get("detected_language", DetectedLanguage.vi)
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
    lang = state.get("detected_language", DetectedLanguage.vi)
    
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
    return {"final_response": "Handled other intent."} # Placeholder for LangGraph router

def build_graph() -> StateGraph:
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
