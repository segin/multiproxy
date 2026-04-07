import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.config import Config, Backend, ModelMapping
from httpx import Response, Request, HTTPStatusError, RequestError

client = TestClient(app)

@pytest.fixture
def mock_config(monkeypatch):
    config = Config(
        backends=[Backend(id="backend1", url="http://fake-backend:8080")],
        model_mappings=[ModelMapping(model_id="test-model", backend_ids=["backend1"])]
    )
    # We will need to patch the global config used by the app.
    # We can assume app.main will have a get_config dependency or global variable.
    # For now, let's patch the load_config or however the app gets it.
    # Since we haven't implemented it yet, we'll patch a hypothetical app.main.current_config
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    return config

def test_proxy_forwards_request(mock_config):
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Ping"}]
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/chat/completions")
    mock_response = Response(
        status_code=200, 
        json={
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Pong"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        },
        request=mock_request
    )
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        response = client.post("/v1/chat/completions", json=payload)
        
        assert response.status_code == 200
        # Verify the 300s timeout was used
        assert mock_post.call_args[1]["timeout"] == 600.0
        data = response.json()
        assert data["choices"][0]["message"]["content"] == "Pong"
        
        # Verify the proxy made the correct outbound request
        mock_post.assert_called_once()
        called_url = str(mock_post.call_args[0][0])
        assert called_url.startswith("http://fake-backend:8080")
        assert "/v1/chat/completions" in called_url

def test_proxy_model_not_found(mock_config):
    payload = {
        "model": "unmapped-model",
        "messages": [{"role": "user", "content": "Ping"}]
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 404

def test_proxy_backend_http_error(mock_config):
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Ping"}]
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/chat/completions")
    mock_response = Response(status_code=500, content=b"Internal Server Error", request=mock_request)
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = HTTPStatusError(
            message="Internal Server Error",
            request=mock_request,
            response=mock_response
        )
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 500

def test_proxy_backend_connection_error(mock_config):
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Ping"}]
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/chat/completions")
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = RequestError(
            message="Connection refused",
            request=mock_request
        )
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 502
        assert "Connection error (RequestError): Connection refused" in response.text

import json
from fastapi.responses import StreamingResponse

def test_proxy_forwards_streaming_request(mock_config):
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Ping"}],
        "stream": True
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/chat/completions")
    
    async def mock_stream_generator():
        yield b'data: {"id": "1", "choices": [{"delta": {"content": "Po"}}]}'
        yield b'\n\n'
        yield b'data: {"id": "1", "choices": [{"delta": {"content": "ng"}}]}'
        yield b'\n\n'
        yield b'data: [DONE]'
        yield b'\n\n'
        
    mock_response = Response(status_code=200, request=mock_request)
    mock_response.aiter_bytes = mock_stream_generator
    
    # We need to mock the context manager returned by stream()
    class MockStreamContextManager:
        async def __aenter__(self):
            return mock_response
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
            
    with patch("httpx.AsyncClient.stream") as mock_stream:
        mock_stream.return_value = MockStreamContextManager()
        
        response = client.post("/v1/chat/completions", json=payload)
        
        assert response.status_code == 200
        # Verify timeout
        assert mock_stream.call_args[1]["timeout"] == 600.0
        # When streaming, the TestClient response has iter_lines()
        lines = list(response.iter_lines())
        
        # Verify the content contains the streamed chunks
        assert 'data: {"id": "1", "choices": [{"delta": {"content": "Po"}}]}' in lines
        assert 'data: {"id": "1", "choices": [{"delta": {"content": "ng"}}]}' in lines
        assert 'data: [DONE]' in lines
def test_proxy_forwards_streaming_request_http_error(mock_config):
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Ping"}],
        "stream": True
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/chat/completions")
    mock_response = Response(status_code=500, content=b"Stream Error", request=mock_request)
    
    class MockStreamContextManagerError:
        async def __aenter__(self):
            raise HTTPStatusError(
                message="Stream Error",
                request=mock_request,
                response=mock_response
            )
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
            
    with patch("httpx.AsyncClient.stream") as mock_stream:
        mock_stream.return_value = MockStreamContextManagerError()
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Stream Error" in content

def test_proxy_forwards_streaming_request_connection_error(mock_config):
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Ping"}],
        "stream": True
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/chat/completions")
    
    class MockStreamContextManagerConnError:
        async def __aenter__(self):
            raise RequestError(
                message="Stream connection refused",
                request=mock_request
            )
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
            
    with patch("httpx.AsyncClient.stream") as mock_stream:
        mock_stream.return_value = MockStreamContextManagerConnError()
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Connection error (RequestError): Stream connection refused" in content

def test_proxy_no_backends_available(monkeypatch):
    config = Config(
        backends=[],
        model_mappings=[ModelMapping(model_id="test-model", backend_ids=["backend1"])]
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Ping"}]
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 503

def test_proxy_rejects_exceeding_context(mock_config):
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Ping"}],
    }
    with patch("app.main.get_backend_limit", return_value=1):
        with patch("app.main.count_tokens", return_value=5):
            response = client.post("/v1/chat/completions", json=payload)
            assert response.status_code == 400
            assert "exceeds the available context size" in response.text
