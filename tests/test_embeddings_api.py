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
        backends=[Backend(id="e1", url="http://embed:8080")],
        model_mappings=[ModelMapping(model_id="embed-model", backend_ids=["e1"])],
        default_embedding_model_id="embed-model",
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    return config


def _embed_response(usage=None):
    mock_request = Request("POST", "http://embed:8080/v1/embeddings")
    body = {
        "object": "list",
        "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
        "model": "embed-model",
    }
    if usage is not None:
        body["usage"] = usage
    return Response(status_code=200, json=body, request=mock_request)


def test_embeddings_string_input(mock_config):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _embed_response({"prompt_tokens": 2, "total_tokens": 2})
        response = client.post("/v1/embeddings", json={"model": "embed-model", "input": "hello"})
        assert response.status_code == 200
        assert response.json()["data"][0]["embedding"] == [0.1, 0.2]


def test_embeddings_string_list_input(mock_config):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _embed_response()
        response = client.post("/v1/embeddings", json={"model": "embed-model", "input": ["a", "b"]})
        assert response.status_code == 200


def test_embeddings_token_list_input(mock_config):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _embed_response()
        response = client.post("/v1/embeddings", json={"model": "embed-model", "input": [1, 2, 3]})
        assert response.status_code == 200


def test_embeddings_falls_back_to_default_embedding_model(mock_config):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
         patch("app.main.log_request") as mock_log:
        mock_post.return_value = _embed_response()
        response = client.post("/v1/embeddings", json={"model": "unknown-embedder", "input": "hi"})
        assert response.status_code == 200
        # Logged under the default embedding model id, not the unknown alias
        assert mock_log.call_args.args[0] == "embed-model"


def test_embeddings_model_not_found(monkeypatch):
    config = Config(backends=[], model_mappings=[])
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    response = client.post("/v1/embeddings", json={"model": "nope", "input": "hi"})
    assert response.status_code == 404


def test_embeddings_no_backends_available(monkeypatch):
    config = Config(
        backends=[],
        model_mappings=[ModelMapping(model_id="embed-model", backend_ids=["gone"])],
        default_embedding_model_id="embed-model",
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    response = client.post("/v1/embeddings", json={"model": "embed-model", "input": "hi"})
    assert response.status_code == 503


def test_embeddings_exceeds_context(mock_config):
    with patch("app.main.get_backend_limit", return_value=1), \
         patch("app.main.count_tokens", return_value=5):
        response = client.post("/v1/embeddings", json={"model": "embed-model", "input": "hi"})
        assert response.status_code == 400
        assert "exceeds the available context size" in response.text


def test_embeddings_backend_http_error(mock_config):
    mock_request = Request("POST", "http://embed:8080/v1/embeddings")
    mock_response = Response(status_code=500, content=b"boom", request=mock_request)
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = HTTPStatusError(message="boom", request=mock_request, response=mock_response)
        response = client.post("/v1/embeddings", json={"model": "embed-model", "input": "hi"})
        assert response.status_code == 500


def test_embeddings_backend_connection_error(mock_config):
    mock_request = Request("POST", "http://embed:8080/v1/embeddings")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = RequestError(message="refused", request=mock_request)
        response = client.post("/v1/embeddings", json={"model": "embed-model", "input": "hi"})
        assert response.status_code == 502
