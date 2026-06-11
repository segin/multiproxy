import pytest
from fastapi.testclient import TestClient
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

def test_list_models_endpoint(mock_config):
    # Mock limits are tested in test_discovery.py
    # Here we just verify the endpoint works and formats data correctly
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()

    assert data["object"] == "list"
    assert "data" in data
    assert len(data["data"]) == 1 # based on mock_config having test-model

    model = data["data"][0]
    assert model["id"] == "test-model"
    assert model["object"] == "model"
    assert "context_length" in model


def test_list_models_reports_max_backend_limit(monkeypatch):
    config = Config(
        backends=[
            Backend(id="b1", url="http://b1:8080"),
            Backend(id="b2", url="http://b2:8080"),
        ],
        model_mappings=[ModelMapping(model_id="chat-model", backend_ids=["b1", "b2"])],
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    monkeypatch.setattr("app.discovery._backend_limits", {"b1": 8192, "b2": 16384}, raising=False)

    response = client.get("/v1/models")
    assert response.status_code == 200
    # Consistent with /v1/models/browser: max across all mapped backends
    assert response.json()["data"][0]["context_length"] == 16384


@pytest.fixture
def browser_config(monkeypatch):
    config = Config(
        backends=[
            Backend(id="b1", url="http://b1:8080"),
            Backend(id="b2", url="http://b2:8080", context_size=16384),
        ],
        model_mappings=[
            ModelMapping(model_id="chat-model", backend_ids=["b1", "b2"]),
            ModelMapping(model_id="embed-model", backend_ids=["b2"]),
            ModelMapping(model_id="orphan-model", backend_ids=["missing-backend"]),
        ],
        default_model_id="chat-model",
        default_embedding_model_id="embed-model",
    )
    monkeypatch.setattr("app.main.current_config", config, raising=False)
    monkeypatch.setattr(
        "app.discovery._backend_limits",
        {"b1": 8192, "b2": 16384},
        raising=False,
    )
    return config


def test_models_browser_endpoint(browser_config):
    response = client.get("/v1/models/browser")
    assert response.status_code == 200
    data = response.json()

    assert data["object"] == "list"
    assert data["default_model_id"] == "chat-model"
    assert data["default_embedding_model_id"] == "embed-model"
    assert len(data["data"]) == 3

    by_id = {m["id"]: m for m in data["data"]}

    chat = by_id["chat-model"]
    assert chat["is_default"] is True
    assert chat["is_default_embedding"] is False
    assert chat["context_length"] == 16384  # max across b1+b2
    assert {b["id"] for b in chat["backends"]} == {"b1", "b2"}
    b1_entry = next(b for b in chat["backends"] if b["id"] == "b1")
    assert b1_entry["url"] == "http://b1:8080"
    assert b1_entry["configured"] is True
    assert b1_entry["context_length"] == 8192

    embed = by_id["embed-model"]
    assert embed["is_default"] is False
    assert embed["is_default_embedding"] is True
    assert embed["context_length"] == 16384

    orphan = by_id["orphan-model"]
    assert orphan["context_length"] is None
    assert orphan["backends"][0]["configured"] is False
    assert orphan["backends"][0]["url"] is None


def test_models_browser_empty_config(monkeypatch):
    config = Config(backends=[], model_mappings=[])
    monkeypatch.setattr("app.main.current_config", config, raising=False)

    response = client.get("/v1/models/browser")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["default_model_id"] is None
    assert data["default_embedding_model_id"] is None
