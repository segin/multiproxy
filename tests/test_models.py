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
