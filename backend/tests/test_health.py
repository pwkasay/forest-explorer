"""Tests for the health endpoint."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    """Health endpoint returns status ok without any DB dependency."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "forest-carbon-explorer"
