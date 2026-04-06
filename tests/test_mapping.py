import pytest
from app.config import Config, Backend, ModelMapping
from app.mapping import get_backend_url, ModelNotFoundError, NoBackendsAvailableError

def test_get_backend_url_single_backend():
    config = Config(
        backends=[Backend(id="b1", url="http://localhost:8081")],
        model_mappings=[ModelMapping(model_id="gpt-5.4", backend_ids=["b1"])]
    )
    url = get_backend_url("gpt-5.4", config)
    assert url == "http://localhost:8081"

def test_get_backend_url_multiple_backends_load_balancing():
    config = Config(
        backends=[
            Backend(id="b1", url="http://localhost:8081"),
            Backend(id="b2", url="http://localhost:8082")
        ],
        model_mappings=[ModelMapping(model_id="claude-opus-4.6", backend_ids=["b1", "b2"])]
    )
    
    # Run multiple times to ensure we get both URLs eventually
    urls_seen = set()
    for _ in range(100):
        url = get_backend_url("claude-opus-4.6", config)
        urls_seen.add(url)
    
    assert "http://localhost:8081" in urls_seen
    assert "http://localhost:8082" in urls_seen

def test_get_backend_url_model_not_found():
    config = Config(
        backends=[Backend(id="b1", url="http://localhost:8081")],
        model_mappings=[ModelMapping(model_id="gpt-5.4", backend_ids=["b1"])]
    )
    with pytest.raises(ModelNotFoundError):
        get_backend_url("nonexistent-model", config)

def test_get_backend_url_default_model_fallback():
    config = Config(
        default_model_id="gpt-5.4",
        backends=[Backend(id="b1", url="http://localhost:8081")],
        model_mappings=[ModelMapping(model_id="gpt-5.4", backend_ids=["b1"])]
    )
    url = get_backend_url("nonexistent-model", config)
    assert url == "http://localhost:8081"

def test_get_backend_url_no_backends_configured():
    config = Config(
        backends=[Backend(id="b1", url="http://localhost:8081")],
        model_mappings=[ModelMapping(model_id="gpt-5.4", backend_ids=["b2"])] # b2 doesn't exist
    )
    with pytest.raises(NoBackendsAvailableError):
        get_backend_url("gpt-5.4", config)
