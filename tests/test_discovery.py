import pytest
from httpx import Response, Request
from unittest.mock import patch, AsyncMock
from app.discovery import discover_backend_limits, get_backend_limit
from app.config import Config, Backend

@pytest.fixture
def mock_config():
    return Config(
        backends=[
            Backend(id="b1", url="http://fake-backend:8080"),
            Backend(id="b2", url="http://fake-backend:8081/v1")
        ],
        model_mappings=[]
    )

@pytest.mark.asyncio
async def test_discover_backend_limits(mock_config):
    # Test valid discovery
    mock_req_1 = Request("GET", "http://fake-backend:8080/props")
    mock_req_2 = Request("GET", "http://fake-backend:8081/props")
    mock_response_b1 = Response(status_code=200, json={"default_generation_settings": {"n_ctx": 4096}}, request=mock_req_1)
    mock_response_b2 = Response(status_code=200, json={"default_generation_settings": {"n_ctx": 8192}}, request=mock_req_2)
    
    async def mock_get(url, *args, **kwargs):
        if "8080" in url:
            return mock_response_b1
        return mock_response_b2
        
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get_patch:
        mock_get_patch.side_effect = mock_get
        await discover_backend_limits(mock_config)
        
        assert get_backend_limit("b1") == 4096
        assert get_backend_limit("b2") == 8192

@pytest.mark.asyncio
async def test_discovery_uses_finite_timeout(mock_config):
    """Startup discovery must not hang forever on an unresponsive backend."""
    from app.discovery import DISCOVERY_TIMEOUT_SECONDS
    mock_req = Request("GET", "http://fake-backend:8080/props")
    mock_response = Response(status_code=200, json={"default_generation_settings": {"n_ctx": 4096}}, request=mock_req)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get_patch:
        mock_get_patch.return_value = mock_response
        await discover_backend_limits(mock_config)
        assert mock_get_patch.call_args.kwargs["timeout"] == DISCOVERY_TIMEOUT_SECONDS


@pytest.mark.asyncio
async def test_discovery_uses_manual_context_size_override():
    config = Config(
        backends=[Backend(id="manual", url="http://fake-backend:8080", context_size=2048)],
        model_mappings=[]
    )
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get_patch:
        await discover_backend_limits(config)
        mock_get_patch.assert_not_called()
        assert get_backend_limit("manual") == 2048


@pytest.mark.asyncio
async def test_discover_backend_limits_error_handling(mock_config):
    # Test fallback if the backend is down or doesn't have /props
    mock_req = Request("GET", "http://fake-backend:8080/props")
    mock_response_err = Response(status_code=500, request=mock_req)
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get_patch:
        mock_get_patch.return_value = mock_response_err
        await discover_backend_limits(mock_config)
        
        # If it fails, it shouldn't crash, and limit might be None or a default
        assert get_backend_limit("b1") is None

@pytest.mark.asyncio
async def test_discover_backend_limits_missing_n_ctx(mock_config):
    mock_req = Request("GET", "http://fake-backend:8080/props")
    mock_response = Response(status_code=200, json={"default_generation_settings": {}}, request=mock_req)
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get_patch:
        mock_get_patch.return_value = mock_response
        await discover_backend_limits(mock_config)
        
        assert get_backend_limit("b1") is None
