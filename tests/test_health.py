from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_api_v1_health_ready_route_registered():
    """Ready endpoint is wired; use `pytest -m integration` when Docker matches `.env`."""
    c = TestClient(app, raise_server_exceptions=False)
    r = c.get("/api/v1/health/ready")
    assert r.status_code in (200, 500)
