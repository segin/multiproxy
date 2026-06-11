"""Regression tests: the Responses API reports usage as input_tokens/output_tokens;
the proxy must tolerate both that and the llama.cpp prompt_tokens style, and
must understand spec-compliant typed stream events."""
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
        model_mappings=[ModelMapping(model_id="gpt-5", backend_ids=["backend1"])]
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    return config


def test_responses_api_spec_compliant_usage_does_not_500(mock_config):
    payload = {"model": "gpt-5", "input": "Hello"}
    mock_request = Request("POST", "http://fake-backend:8080/v1/responses")
    mock_response = Response(
        status_code=200,
        json={
            "id": "resp-1",
            "object": "response",
            "model": "gpt-5",
            "output": [{"type": "text", "text": "Hi"}],
            "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        },
        request=mock_request,
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
         patch("app.main.log_request") as mock_log:
        mock_post.return_value = mock_response
        response = client.post("/v1/responses", json=payload)
        assert response.status_code == 200

        usage = mock_log.call_args.args[4]
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 20
        assert usage.total_tokens == 30


def test_responses_api_non_streaming_without_usage(mock_config):
    payload = {"model": "gpt-5", "input": "Hello"}
    mock_request = Request("POST", "http://fake-backend:8080/v1/responses")
    mock_response = Response(
        status_code=200,
        json={"id": "resp-1", "object": "response", "model": "gpt-5", "output": []},
        request=mock_request,
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        response = client.post("/v1/responses", json=payload)
        assert response.status_code == 200


def test_responses_streaming_typed_events(mock_config):
    payload = {"model": "gpt-5", "input": "Hello", "stream": True}
    mock_request = Request("POST", "http://fake-backend:8080/v1/responses")

    async def gen():
        yield 'data: {"type": "response.output_text.delta", "delta": "Hi "}'
        yield 'data: {"type": "response.output_text.delta", "delta": "there"}'
        yield 'data: {"type": "response.completed", "response": {"usage": {"input_tokens": 5, "output_tokens": 9}}}'
        yield 'data: [DONE]'

    mock_response = Response(status_code=200, request=mock_request)
    mock_response.aiter_lines = gen

    class CM:
        async def __aenter__(self):
            return mock_response
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("httpx.AsyncClient.stream") as mock_stream, \
         patch("app.main.log_request") as mock_log:
        mock_stream.return_value = CM()
        response = client.post("/v1/responses", json=payload)
        assert response.status_code == 200
        lines = list(response.iter_lines())
        assert 'data: {"type": "response.output_text.delta", "delta": "Hi "}' in lines

        usage = mock_log.call_args.args[4]
        assert usage.prompt_tokens == 5
        assert usage.completion_tokens == 9
        # TTFT must have been measured from the first delta event
        assert mock_log.call_args.args[6] is not None
