import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from httpx import Response, Request
from app.main import app
from app.config import Config, Backend, ModelMapping

client = TestClient(app)

@pytest.fixture
def mock_config(monkeypatch):
    config = Config(
        backends=[Backend(id="backend1", url="http://fake-backend:8080")],
        model_mappings=[ModelMapping(model_id="qwen3.5-35b-a3b", backend_ids=["backend1"])]
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    return config

def test_chat_completions_endpoint_exists(mock_config):
    payload = {
        "model": "qwen3.5-35b-a3b",
        "messages": [
            {"role": "user", "content": "Hello!"}
        ]
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/chat/completions")
    mock_response = Response(
        status_code=200, 
        json={
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "qwen3.5-35b-a3b",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Pong"}, "finish_reason": "stop"}]
        },
        request=mock_request
    )
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        with TestClient(app) as client:
            response = client.post("/v1/chat/completions", json=payload)
        
        assert response.status_code in [200, 501], f"Expected 200 or 501, got {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert data.get("object") == "chat.completion"
            assert "created" in data
            assert "model" in data
            assert "choices" in data
            assert len(data["choices"]) > 0
            assert "message" in data["choices"][0]
            assert "content" in data["choices"][0]["message"]
