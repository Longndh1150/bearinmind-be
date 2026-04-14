from app.ai.graphs.smoke import build_smoke_graph


def test_langgraph_smoke_runs():
    g = build_smoke_graph()
    out = g.invoke({"message": "test"})
    assert out["message"] == "testok"
