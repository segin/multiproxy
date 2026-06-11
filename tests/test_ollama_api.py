import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from httpx import Response, Request, RequestError
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


def _ollama_response(path):
    mock_request = Request("POST", f"http://embed:8080{path}")
    return Response(
        status_code=200,
        json={"model": "embed-model", "embeddings": [[0.1, 0.2]], "prompt_eval_count": 5},
        request=mock_request,
    )


@pytest.mark.parametrize("path", ["/api/embed", "/api/embeddings"])
def test_ollama_passthrough_success(mock_config, path):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
         patch("app.main.log_request") as mock_log:
        mock_post.return_value = _ollama_response(path)
        response = client.post(path, json={"model": "embed-model", "input": "hi"})
        assert response.status_code == 200
        assert response.json()["embeddings"] == [[0.1, 0.2]]

        called_url = str(mock_post.call_args.args[0])
        assert called_url == f"http://embed:8080{path}"
        usage = mock_log.call_args.args[4]
        assert usage.prompt_tokens == 5


def test_ollama_passthrough_invalid_json(mock_config):
    response = client.post(
        "/api/embed",
        content=b"this is not json",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400
    assert "Invalid JSON body" in response.text


def test_ollama_passthrough_missing_model(mock_config):
    response = client.post("/api/embed", json={"input": "hi"})
    assert response.status_code == 400
    assert "'model' field is required" in response.text


def test_ollama_passthrough_model_not_found(monkeypatch):
    config = Config(backends=[], model_mappings=[])
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    response = client.post("/api/embed", json={"model": "nope", "input": "hi"})
    assert response.status_code == 404


def test_ollama_passthrough_connection_error(mock_config):
    mock_request = Request("POST", "http://embed:8080/api/embed")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = RequestError(message="refused", request=mock_request)
        response = client.post("/api/embed", json={"model": "embed-model", "input": "hi"})
        assert response.status_code == 502
