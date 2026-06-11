"""Regression tests: omitted OpenAI sampling params must not be injected into
the backend payload (they would override llama-server's configured defaults)."""
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
        model_mappings=[ModelMapping(model_id="test-model", backend_ids=["backend1"])]
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    return config


def _chat_response():
    mock_request = Request("POST", "http://fake-backend:8080/v1/chat/completions")
    return Response(
        status_code=200,
        json={
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 0,
            "model": "test-model",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Pong"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
        request=mock_request,
    )


def test_omitted_sampling_params_are_not_forwarded(mock_config):
    payload = {"model": "test-model", "messages": [{"role": "user", "content": "Ping"}]}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _chat_response()
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200

        sent = mock_post.call_args.kwargs["json"]
        for param in ("temperature", "top_p", "n", "presence_penalty", "frequency_penalty"):
            assert param not in sent, f"{param} was injected into the backend payload"


def test_explicit_sampling_params_are_forwarded(mock_config):
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Ping"}],
        "temperature": 0.2,
        "top_p": 0.9,
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _chat_response()
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200

        sent = mock_post.call_args.kwargs["json"]
        assert sent["temperature"] == 0.2
        assert sent["top_p"] == 0.9


def test_streaming_forces_include_usage(mock_config):
    payload = {"model": "test-model", "messages": [{"role": "user", "content": "Ping"}], "stream": True}

    mock_request = Request("POST", "http://fake-backend:8080/v1/chat/completions")

    async def mock_stream_generator():
        yield 'data: [DONE]'

    mock_response = Response(status_code=200, request=mock_request)
    mock_response.aiter_lines = mock_stream_generator

    class MockStreamContextManager:
        async def __aenter__(self):
            return mock_response
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("httpx.AsyncClient.stream") as mock_stream:
        mock_stream.return_value = MockStreamContextManager()
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        list(response.iter_lines())

        sent = mock_stream.call_args.kwargs["json"]
        assert sent["stream_options"]["include_usage"] is True


def test_streaming_preserves_existing_stream_options(mock_config):
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Ping"}],
        "stream": True,
        "stream_options": {"chunk_size": 1},
    }

    mock_request = Request("POST", "http://fake-backend:8080/v1/chat/completions")

    async def mock_stream_generator():
        yield 'data: [DONE]'

    mock_response = Response(status_code=200, request=mock_request)
    mock_response.aiter_lines = mock_stream_generator

    class MockStreamContextManager:
        async def __aenter__(self):
            return mock_response
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("httpx.AsyncClient.stream") as mock_stream:
        mock_stream.return_value = MockStreamContextManager()
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        list(response.iter_lines())

        sent = mock_stream.call_args.kwargs["json"]
        assert sent["stream_options"] == {"chunk_size": 1, "include_usage": True}
