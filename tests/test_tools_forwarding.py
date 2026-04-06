from fastapi.testclient import TestClient
from app.main import app
from app.config import Config, Backend, ModelMapping
from unittest.mock import patch, AsyncMock
import httpx
from httpx import Response, Request

client = TestClient(app)

def test_proxy_forwards_tools(monkeypatch):
    config = Config(
        backends=[Backend(id="b1", url="http://fake-backend:8080")],
        model_mappings=[ModelMapping(model_id="test-model", backend_ids=["b1"])]
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "What's the weather like?"}],
        "tools": [
            {"type": "function", "function": {"name": "get_weather", "description": "Get weather"}}
        ],
        "tool_choice": "auto"
    }
    
    mock_req = Request("POST", "http://fake-backend:8080/v1/chat/completions")
    mock_resp = Response(200, json={"id": "chatcmpl-123", "choices": []}, request=mock_req)
    
    async def mock_post(*args, **kwargs):
        assert "tools" in kwargs["json"]
        assert kwargs["json"]["tools"][0]["function"]["name"] == "get_weather"
        assert kwargs["json"]["tool_choice"] == "auto"
        return mock_resp
        
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post_patch:
        mock_post_patch.side_effect = mock_post
        with patch("app.main.get_backend_limit", return_value=4096):
            response = client.post("/v1/chat/completions", json=payload)
            assert response.status_code == 200
