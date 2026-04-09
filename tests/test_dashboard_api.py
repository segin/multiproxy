import pytest
from fastapi.testclient import TestClient
from app.dashboard import app
from app.logger import init_db, clear_logs, log_request
from app.schemas import UsageInfo

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_path = tmp_path / "test_dashboard_api_local.db"
    init_db(str(db_path))
    clear_logs()
    
    # Insert some dummy data
    log_request("model-api", "http://back-api", 200, 150.0, UsageInfo(prompt_tokens=10, completion_tokens=20, total_tokens=30))
    
    yield

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

def test_api_stats_html():
    response = client.get("/api/stats/html")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Total Requests" in response.text

def test_api_logs_html():
    response = client.get("/api/logs/html?limit=10&offset=0")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "model-api" in response.text

def test_api_system_logs_html():
    import logging
    # TestClient context manager to trigger lifespan and logging setup
    with TestClient(app) as client:
        logging.getLogger("test_logger").info("Test system log message")
        response = client.get("/api/system-logs/html?limit=10")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Test system log message" in response.text
