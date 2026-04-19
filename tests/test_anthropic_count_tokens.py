import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from httpx import Response, Request, HTTPStatusError, RequestError
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
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/messages/count_tokens")
    mock_response = Response(
        status_code=200, 
        json={"input_tokens": 42},
        request=mock_request
    )
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        response = client.post("/v1/messages/count_tokens", json=payload)
        
        assert response.status_code == 200
        assert "input_tokens" in response.json()
        assert response.json()["input_tokens"] == 42
        
        mock_post.assert_called_once()
        called_url = str(mock_post.call_args[0][0])
        assert called_url.startswith("http://fake-backend:8080")
        assert "/v1/messages/count_tokens" in called_url

def test_anthropic_count_tokens_not_found():
    payload = {
        "model": "unknown",
        "messages": [{"role": "user", "content": "Hello world"}]
    }
    response = client.post("/v1/messages/count_tokens", json=payload)
    assert response.status_code == 404

def test_anthropic_count_tokens_backend_http_error(mock_config):
    payload = {
        "model": "claude-3",
        "messages": [{"role": "user", "content": "Hello world"}]
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/messages/count_tokens")
    mock_response = Response(status_code=500, content=b"Internal Server Error", request=mock_request)
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = HTTPStatusError(
            message="Internal Server Error",
            request=mock_request,
            response=mock_response
        )
        response = client.post("/v1/messages/count_tokens", json=payload)
        assert response.status_code == 500

def test_anthropic_count_tokens_internal_error(mock_config):
    payload = {
        "model": "claude-3",
        "messages": [{"role": "user", "content": "Hello world"}]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = Exception("Some unknown error")
        response = client.post("/v1/messages/count_tokens", json=payload)
        assert response.status_code == 500

def test_anthropic_count_tokens_backend_connection_error(mock_config):
    payload = {
        "model": "claude-3",
        "messages": [{"role": "user", "content": "Hello world"}]
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/messages/count_tokens")
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = RequestError(
            message="Connection refused",
            request=mock_request
        )
        response = client.post("/v1/messages/count_tokens", json=payload)
        assert response.status_code == 502

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

