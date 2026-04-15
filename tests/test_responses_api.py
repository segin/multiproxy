import pytest
from app.schemas import ResponsesRequest, ResponsesResponse, ResponseItem

def test_responses_schema():
    req = ResponsesRequest(
        model="gpt-5",
        instructions="You are a helpful assistant.",
        input="Hello",
        stream=False
    )
    assert req.model == "gpt-5"
    assert req.input == "Hello"

    resp = ResponsesResponse(
        id="resp-123",
        model="gpt-5",
        output=[ResponseItem(type="text", text="Hi there")]
    )
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from httpx import Response, Request, HTTPStatusError, RequestError

def test_responses_api_model_not_found(mock_config):
    payload = {
        "model": "unmapped-model",
        "input": "Hello",
    }
    response = client.post("/v1/responses", json=payload)
    assert response.status_code == 404

def test_responses_api_no_backends_available(monkeypatch):
    config = Config(
        backends=[],
        model_mappings=[ModelMapping(model_id="gpt-5", backend_ids=["backend1"])]
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    
    payload = {
        "model": "gpt-5",
        "input": "Hello"
    }
    response = client.post("/v1/responses", json=payload)
    assert response.status_code == 503

def test_responses_api_backend_connection_error(mock_config):
    payload = {
        "model": "gpt-5",
        "input": "Hello"
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/responses")
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = RequestError(
            message="Connection refused",
            request=mock_request
        )
        response = client.post("/v1/responses", json=payload)
        assert response.status_code == 502

def test_responses_api_backend_http_error(mock_config):
    payload = {
        "model": "gpt-5",
        "input": "Hello"
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/responses")
    mock_response = Response(status_code=500, content=b"Internal Server Error", request=mock_request)
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = HTTPStatusError(
            message="Internal Server Error",
            request=mock_request,
            response=mock_response
        )
        response = client.post("/v1/responses", json=payload)
        assert response.status_code == 500

def test_responses_api_internal_error(mock_config):
    payload = {
        "model": "gpt-5",
        "input": "Hello"
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = Exception("Some unknown error")
        response = client.post("/v1/responses", json=payload)
        assert response.status_code == 500

def test_responses_api_streaming(mock_config):
    payload = {
        "model": "gpt-5",
        "input": "Hello",
        "stream": True
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/responses")
    
    async def mock_stream_generator():
        yield 'data: {"id": "1", "output": [{"type": "text", "text": "Hi "}]}'
        yield '\n\n'
        yield 'data: {"id": "1", "output": [{"type": "message", "message": {"role": "assistant", "content": "there"}}]}'
        yield '\n\n'
        yield 'data: [DONE]'
        yield '\n\n'
        
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
            response = client.post("/v1/responses", json=payload)
            
            assert response.status_code == 200
            assert mock_stream.call_args[1]["timeout"] == 600.0
            
            lines = list(response.iter_lines())
            assert 'data: {"id": "1", "output": [{"type": "text", "text": "Hi "}]}' in lines
            assert 'data: [DONE]' in lines

def test_responses_api_streaming_error(mock_config):
    payload = {
        "model": "gpt-5",
        "input": "Hello",
        "stream": True
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/responses")
    
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
        response = client.post("/v1/responses", json=payload)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Connection error (RequestError): Stream connection refused" in content

    payload = {
        "model": "gpt-5",
        "input": "Hello",
    }
    with patch("app.main.get_backend_limit", return_value=1):
        with patch("app.main.count_tokens", return_value=5):
            response = client.post("/v1/responses", json=payload)
            assert response.status_code == 400
            assert "exceeds the available context size" in response.text
from app.main import app
from app.config import Config, Backend, ModelMapping

client = TestClient(app)

@pytest.fixture
def mock_config(monkeypatch):
    config = Config(
        backends=[Backend(id="backend1", url="http://fake-backend:8080")],
        model_mappings=[ModelMapping(model_id="gpt-5", backend_ids=["backend1"])]
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    return config

def test_responses_api_non_streaming(mock_config):
    payload = {
        "model": "gpt-5",
        "instructions": "You are a helpful assistant.",
        "input": "Hello",
        "stream": False
    }
    
    mock_request = Request("POST", "http://fake-backend:8080/v1/responses")
    mock_response = Response(
        status_code=200, 
        json={
            "id": "resp-123",
            "object": "response",
            "created": 1234567890,
            "model": "gpt-5",
            "output": [{"type": "text", "text": "Hi there"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        },
        request=mock_request
    )
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        with patch("app.main.get_backend_limit", return_value=4096):
            response = client.post("/v1/responses", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert data["output"][0]["text"] == "Hi there"
            mock_post.assert_called_once()
            called_url = str(mock_post.call_args[0][0])
            assert called_url.startswith("http://fake-backend:8080")
            assert "/v1/responses" in called_url
