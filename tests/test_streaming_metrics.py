"""Streaming metrics and error-path tests: backend usage wins over local counts,
Anthropic message_delta usage is cumulative (assigned, not accumulated), and
stream failures surface as SSE error events while still being logged."""
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from httpx import Response, Request
from app.main import app
from app.config import Config, Backend, ModelMapping

client = TestClient(app)


@pytest.fixture
def mock_config(monkeypatch):
    config = Config(
        backends=[Backend(id="backend1", url="http://fake-backend:8080")],
        model_mappings=[
            ModelMapping(model_id="test-model", backend_ids=["backend1"]),
            ModelMapping(model_id="claude-3", backend_ids=["backend1"]),
        ]
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    return config


def _stream_cm(lines):
    mock_request = Request("POST", "http://fake-backend:8080/v1/chat/completions")
    mock_response = Response(status_code=200, request=mock_request)

    async def gen():
        for line in lines:
            yield line

    mock_response.aiter_lines = gen

    class CM:
        async def __aenter__(self):
            return mock_response
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    return CM()


def test_chat_stream_uses_backend_usage(mock_config):
    payload = {"model": "test-model", "messages": [{"role": "user", "content": "Ping"}], "stream": True}
    lines = [
        'data: {"id": "1", "choices": [{"delta": {"content": "Po"}}]}',
        'data: {"id": "1", "choices": [{"delta": {"content": "ng"}}]}',
        'data: {"id": "1", "choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 42, "total_tokens": 49}}',
        'data: [DONE]',
    ]

    with patch("httpx.AsyncClient.stream") as mock_stream, \
         patch("app.main.log_request") as mock_log:
        mock_stream.return_value = _stream_cm(lines)
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        list(response.iter_lines())

        mock_log.assert_called_once()
        usage = mock_log.call_args.args[4]
        assert usage.prompt_tokens == 7
        assert usage.completion_tokens == 42
        assert usage.total_tokens == 49


def test_chat_stream_counts_tokens_when_usage_missing(mock_config):
    payload = {"model": "test-model", "messages": [{"role": "user", "content": "Ping"}], "stream": True}
    lines = [
        'data: {"id": "1", "choices": [{"delta": {"content": "Hello world"}}]}',
        'data: [DONE]',
    ]

    with patch("httpx.AsyncClient.stream") as mock_stream, \
         patch("app.main.log_request") as mock_log:
        mock_stream.return_value = _stream_cm(lines)
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        list(response.iter_lines())

        usage = mock_log.call_args.args[4]
        assert usage.completion_tokens > 0  # tiktoken fallback on accumulated content


def test_chat_stream_tolerates_invalid_json_chunks(mock_config):
    payload = {"model": "test-model", "messages": [{"role": "user", "content": "Ping"}], "stream": True}
    lines = [
        'data: this-is-not-json',
        'data: {"id": "1", "choices": [{"delta": {"content": "ok"}}]}',
        'data: [DONE]',
    ]

    with patch("httpx.AsyncClient.stream") as mock_stream:
        mock_stream.return_value = _stream_cm(lines)
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        body_lines = list(response.iter_lines())
        # Malformed chunks are passed through untouched
        assert 'data: this-is-not-json' in body_lines
        assert 'data: [DONE]' in body_lines


def test_chat_stream_internal_error_yields_sse_error(mock_config):
    payload = {"model": "test-model", "messages": [{"role": "user", "content": "Ping"}], "stream": True}
    mock_request = Request("POST", "http://fake-backend:8080/v1/chat/completions")
    mock_response = Response(status_code=200, request=mock_request)

    async def exploding_gen():
        yield 'data: {"id": "1", "choices": [{"delta": {"content": "x"}}]}'
        raise RuntimeError("kaboom")

    mock_response.aiter_lines = exploding_gen

    class CM:
        async def __aenter__(self):
            return mock_response
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("httpx.AsyncClient.stream") as mock_stream:
        mock_stream.return_value = CM()
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Internal proxy stream error (RuntimeError): kaboom" in content
        assert "data: [DONE]" in content


def test_chat_stream_backend_json_error_passthrough(mock_config):
    """HTTPStatusError whose body already carries an OpenAI-style error object."""
    from httpx import HTTPStatusError
    payload = {"model": "test-model", "messages": [{"role": "user", "content": "Ping"}], "stream": True}
    mock_request = Request("POST", "http://fake-backend:8080/v1/chat/completions")
    error_body = json.dumps({"error": {"message": "backend says no", "type": "rate_limit"}})
    mock_response = Response(status_code=429, content=error_body.encode(), request=mock_request)

    class CM:
        async def __aenter__(self):
            raise HTTPStatusError(message="429", request=mock_request, response=mock_response)
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("httpx.AsyncClient.stream") as mock_stream:
        mock_stream.return_value = CM()
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        assert "backend says no" in response.content.decode()


def test_anthropic_stream_usage_is_cumulative_not_summed(mock_config):
    """message_delta usage carries cumulative totals; they must be assigned."""
    payload = {"model": "claude-3", "messages": [{"role": "user", "content": "Hello"}], "stream": True}
    lines = [
        'data: {"type": "message_start", "message": {"usage": {"input_tokens": 10, "output_tokens": 2, "cache_read_input_tokens": 4}}}',
        'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi there"}}',
        'data: {"type": "message_delta", "usage": {"output_tokens": 20}}',
        'data: [DONE]',
    ]

    with patch("httpx.AsyncClient.stream") as mock_stream, \
         patch("app.main.log_request") as mock_log:
        mock_stream.return_value = _stream_cm(lines)
        response = client.post("/v1/messages", json=payload)
        assert response.status_code == 200
        list(response.iter_lines())

        usage = mock_log.call_args.args[4]
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 20  # not 22: cumulative, not summed
        assert usage.total_tokens == 30
        assert usage.cache_read_input_tokens == 4


def test_anthropic_stream_error_is_wellformed_sse(mock_config):
    """Anthropic-style stream errors must put the event line before the data line."""
    from httpx import RequestError
    payload = {"model": "claude-3", "messages": [{"role": "user", "content": "Hello"}], "stream": True}
    mock_request = Request("POST", "http://fake-backend:8080/v1/messages")

    class CM:
        async def __aenter__(self):
            raise RequestError(message="boom", request=mock_request)
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("httpx.AsyncClient.stream") as mock_stream:
        mock_stream.return_value = CM()
        response = client.post("/v1/messages", json=payload)
        assert response.status_code == 200
        content = response.content.decode()
        assert "event: error\ndata: " in content
