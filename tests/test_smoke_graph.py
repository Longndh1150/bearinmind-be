from typing import TypedDict

from langgraph.graph import END, StateGraph


class SmokeState(TypedDict, total=False):
    message: str


def _step(state: SmokeState) -> SmokeState:
    return {"message": (state.get("message") or "") + "ok"}


def build_smoke_graph():
    g = StateGraph(SmokeState)
    g.add_node("step", _step)
    g.set_entry_point("step")
    g.add_edge("step", END)
    return g.compile()


def test_langgraph_smoke_runs():
    g = build_smoke_graph()
    out = g.invoke({"message": "test"})
    assert out["message"] == "testok"
