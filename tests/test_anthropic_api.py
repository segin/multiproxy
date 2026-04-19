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

def test_anthropic_api_non_streaming(mock_config):
    payload = {
        "model": "claude-3",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/messages")
    mock_response = Response(
        status_code=200, 
        json={
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "model": "claude-3",
            "content": [{"type": "text", "text": "Hi there"}],
            "usage": {"input_tokens": 10, "output_tokens": 20}
        },
        request=mock_request
    )
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        with patch("app.main.get_backend_limit", return_value=4096):
            response = client.post("/v1/messages", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert data["content"][0]["text"] == "Hi there"

def test_anthropic_api_streaming(mock_config):
    payload = {
        "model": "claude-3",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/messages")
    
    async def mock_stream_generator():
        yield 'data: {"type": "message_start", "message": {"usage": {"input_tokens": 10}}}\n\n'
        yield 'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi "}}\n\n'
        yield 'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "there"}}\n\n'
        yield 'data: {"type": "message_delta", "usage": {"output_tokens": 20}}\n\n'
        yield 'data: [DONE]\n\n'
        
    mock_response = Response(status_code=200, request=mock_request)
    mock_response.aiter_lines = mock_stream_generator
    
    class MockStreamContextManager:
        async def __aenter__(self):
            return mock_response
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
            
    with patch("httpx.AsyncClient.stream") as mock_stream:
        mock_stream.return_value = MockStreamContextManager()
        with patch("app.main.get_backend_limit", return_value=4096):
            response = client.post("/v1/messages", json=payload)
            
            assert response.status_code == 200
            
            lines = list(response.iter_lines())
            assert 'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi "}}' in lines

def test_anthropic_api_error_handling(mock_config):
    payload = {
        "model": "unmapped",
        "messages": [{"role": "user", "content": "Hello"}],
    }
    response = client.post("/v1/messages", json=payload)
    assert response.status_code == 404

def test_anthropic_api_no_backends_available(monkeypatch):
    config = Config(
        backends=[],
        model_mappings=[ModelMapping(model_id="claude-3", backend_ids=["backend1"])]
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    
    payload = {
        "model": "claude-3",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    response = client.post("/v1/messages", json=payload)
    assert response.status_code == 503

def test_anthropic_api_exceeds_context(mock_config):
    payload = {
        "model": "claude-3",
        "messages": [{"role": "user", "content": "Hello"}],
    }
    with patch("app.main.get_backend_limit", return_value=1):
        with patch("app.main.count_tokens", return_value=5):
            response = client.post("/v1/messages", json=payload)
            assert response.status_code == 400
            assert "exceeds the available context size" in response.text

def test_anthropic_api_backend_http_error(mock_config):
    payload = {
        "model": "claude-3",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/messages")
    mock_response = Response(status_code=500, content=b"Internal Server Error", request=mock_request)
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = HTTPStatusError(
            message="Internal Server Error",
            request=mock_request,
            response=mock_response
        )
        response = client.post("/v1/messages", json=payload)
        assert response.status_code == 500

def test_anthropic_api_internal_error(mock_config):
    payload = {
        "model": "claude-3",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = Exception("Some unknown error")
        response = client.post("/v1/messages", json=payload)
        assert response.status_code == 500

def test_anthropic_api_backend_connection_error(mock_config):
    payload = {
        "model": "claude-3",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/messages")
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = RequestError(
            message="Connection refused",
            request=mock_request
        )
        response = client.post("/v1/messages", json=payload)
        assert response.status_code == 502

def test_anthropic_api_streaming_error(mock_config):
    payload = {
        "model": "claude-3",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/messages")
    
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
        response = client.post("/v1/messages", json=payload)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Connection error (RequestError): Stream connection refused" in content

def test_anthropic_api_streaming_http_error(mock_config):
    payload = {
        "model": "claude-3",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/messages")
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
        response = client.post("/v1/messages", json=payload)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Stream Error" in content
