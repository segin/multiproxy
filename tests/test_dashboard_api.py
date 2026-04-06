import pytest
from fastapi.testclient import TestClient
from app.dashboard import app
from app.logger import init_db, clear_logs, log_request
from app.schemas import UsageInfo

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_path = tmp_path / "test_dashboard_api.db"
    init_db(str(db_path))
    clear_logs()
    
    # Insert some dummy data
    log_request("model-api", "http://back-api", 200, 150.0, UsageInfo(prompt_tokens=10, completion_tokens=20, total_tokens=30))
    
    yield
    init_db("logs.db")

def test_api_stats():
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_requests" in data
    assert data["total_requests"] == 1
    assert data["total_tokens"] == 30

def test_api_logs():
    response = client.get("/api/logs?limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["model_id"] == "model-api"
