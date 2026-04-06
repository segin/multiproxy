from fastapi.testclient import TestClient
from app.dashboard import app

client = TestClient(app)

def test_dashboard_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_dashboard_index_template():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
