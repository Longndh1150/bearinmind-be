import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
def require_services():
    if os.getenv("SKIP_INTEGRATION", "").lower() in ("1", "true", "yes"):
        pytest.skip("SKIP_INTEGRATION=1")


def test_health_ready_all_green(require_services):
    client = TestClient(app)
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    for key in ("database", "redis", "chroma"):
        assert key in body["checks"]
        assert body["checks"][key] == "connected"
