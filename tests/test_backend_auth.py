import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from httpx import Response, Request
from app.main import app, backend_auth_headers
from app.config import Config, Backend, ModelMapping

client = TestClient(app)


def _mock_post_response(url: str, body: dict) -> Response:
    return Response(status_code=200, json=body, request=Request("POST", url))


@pytest.fixture
def keyed_chat_config(monkeypatch):
    config = Config(
        backends=[Backend(id="b1", url="http://backend:8080", api_key="sk-secret")],
        model_mappings=[ModelMapping(model_id="chat-model", backend_ids=["b1"])],
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    return config


@pytest.fixture
def keyless_chat_config(monkeypatch):
    config = Config(
        backends=[Backend(id="b1", url="http://backend:8080")],
        model_mappings=[ModelMapping(model_id="chat-model", backend_ids=["b1"])],
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    return config


def test_helper_openai_with_key():
    backend = Backend(id="x", url="http://x", api_key="sk-abc")
    assert backend_auth_headers(backend) == {"Authorization": "Bearer sk-abc"}


def test_helper_openai_without_key():
    backend = Backend(id="x", url="http://x")
    assert backend_auth_headers(backend) == {}


def test_helper_anthropic_with_key():
    backend = Backend(id="x", url="http://x", api_key="sk-ant-1")
    headers = backend_auth_headers(backend, anthropic=True)
    assert headers["x-api-key"] == "sk-ant-1"
    assert headers["anthropic-version"] == "2023-06-01"


def test_helper_anthropic_without_key_preserves_dummy():
    backend = Backend(id="x", url="http://x")
    headers = backend_auth_headers(backend, anthropic=True)
    assert headers["x-api-key"] == "sk-dummy"
    assert headers["anthropic-version"] == "2023-06-01"


def test_chat_completions_forwards_bearer_when_key_set(keyed_chat_config):
    payload = {"model": "chat-model", "messages": [{"role": "user", "content": "hi"}]}
    body = {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "chat-model",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_post_response("http://backend:8080/v1/chat/completions", body)
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        sent_headers = mock_post.call_args.kwargs["headers"]
        assert sent_headers == {"Authorization": "Bearer sk-secret"}


def test_chat_completions_omits_auth_when_key_unset(keyless_chat_config):
    payload = {"model": "chat-model", "messages": [{"role": "user", "content": "hi"}]}
    body = {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "chat-model",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_post_response("http://backend:8080/v1/chat/completions", body)
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        sent_headers = mock_post.call_args.kwargs["headers"]
        assert "Authorization" not in sent_headers


def test_messages_forwards_anthropic_key_when_set(monkeypatch):
    config = Config(
        backends=[Backend(id="b1", url="http://backend:8080", api_key="sk-ant-secret")],
        model_mappings=[ModelMapping(model_id="claude-test", backend_ids=["b1"])],
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)

    payload = {"model": "claude-test", "messages": [{"role": "user", "content": "hi"}]}
    body = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "hi"}],
        "model": "claude-test",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_post_response("http://backend:8080/v1/messages", body)
        response = client.post("/v1/messages", json=payload)
        assert response.status_code == 200
        sent_headers = mock_post.call_args.kwargs["headers"]
        assert sent_headers["x-api-key"] == "sk-ant-secret"
        assert sent_headers["anthropic-version"] == "2023-06-01"


def test_messages_preserves_dummy_key_when_unset(monkeypatch):
    config = Config(
        backends=[Backend(id="b1", url="http://backend:8080")],
        model_mappings=[ModelMapping(model_id="claude-test", backend_ids=["b1"])],
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)

    payload = {"model": "claude-test", "messages": [{"role": "user", "content": "hi"}]}
    body = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "hi"}],
        "model": "claude-test",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_post_response("http://backend:8080/v1/messages", body)
        response = client.post("/v1/messages", json=payload)
        assert response.status_code == 200
        sent_headers = mock_post.call_args.kwargs["headers"]
        assert sent_headers["x-api-key"] == "sk-dummy"


def test_embeddings_forwards_bearer_when_key_set(monkeypatch):
    config = Config(
        backends=[Backend(id="e1", url="http://embed:8080", api_key="sk-embed")],
        model_mappings=[ModelMapping(model_id="embed-model", backend_ids=["e1"])],
        default_embedding_model_id="embed-model",
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)

    body = {
        "object": "list",
        "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
        "model": "embed-model",
        "usage": {"prompt_tokens": 2, "total_tokens": 2},
    }
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_post_response("http://embed:8080/v1/embeddings", body)
        response = client.post("/v1/embeddings", json={"model": "embed-model", "input": "hi"})
        assert response.status_code == 200
        sent_headers = mock_post.call_args.kwargs["headers"]
        assert sent_headers == {"Authorization": "Bearer sk-embed"}
