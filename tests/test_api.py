from fastapi.testclient import TestClient

from control_tower.api import app


def test_health_endpoint_has_known_state():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "data_missing"}

