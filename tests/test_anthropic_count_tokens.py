import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app
from app.config import Config, Backend, ModelMapping

client = TestClient(app)

@pytest.fixture
def mock_config(monkeypatch):
    config = Config(
        backends=[Backend(id="backend1", url="http://fake-backend:8080")],
        model_mappings=[ModelMapping(model_id="claude-3", backend_ids=["backend1"])]
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    return config

def test_anthropic_count_tokens(mock_config):
    payload = {
        "model": "claude-3",
        "messages": [{"role": "user", "content": "Hello world"}]
    }
    response = client.post("/v1/messages/count_tokens", json=payload)
    assert response.status_code == 200
    assert "input_tokens" in response.json()

def test_anthropic_count_tokens_not_found():
    payload = {
        "model": "unknown",
        "messages": [{"role": "user", "content": "Hello world"}]
    }
    response = client.post("/v1/messages/count_tokens", json=payload)
    assert response.status_code == 404

def test_anthropic_count_tokens_no_backends(monkeypatch):
    config = Config(
        backends=[],
        model_mappings=[ModelMapping(model_id="claude-3", backend_ids=["backend1"])]
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    
    payload = {
        "model": "claude-3",
        "messages": [{"role": "user", "content": "Hello world"}]
    }
    response = client.post("/v1/messages/count_tokens", json=payload)
    assert response.status_code == 503

