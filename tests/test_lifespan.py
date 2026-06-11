import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.config import Config


@pytest.fixture(autouse=True)
def restore_current_config():
    saved = main_module.current_config
    yield
    main_module.current_config = saved


def test_lifespan_loads_config_and_discovers_limits():
    cfg = Config(backends=[], model_mappings=[], untracked_models=[])
    with patch("app.main.load_config", return_value=cfg) as mock_load, \
         patch("app.main.discover_backend_limits", new_callable=AsyncMock) as mock_discover:
        with TestClient(app):
            pass
        mock_load.assert_called_once_with("config.yaml")
        mock_discover.assert_awaited_once_with(cfg)


def test_lifespan_handles_missing_config():
    with patch("app.main.load_config", side_effect=FileNotFoundError) as mock_load, \
         patch("app.main.discover_backend_limits", new_callable=AsyncMock) as mock_discover:
        with TestClient(app):
            pass
        mock_load.assert_called_once()
        mock_discover.assert_awaited_once()
