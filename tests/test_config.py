import pytest
import yaml
from pathlib import Path
from pydantic import ValidationError

from app.config import load_config, Config, Backend, ModelMapping

def test_load_valid_config(tmp_path: Path):
    config_data = {
        "backends": [
            {"id": "llama-server-1", "url": "http://localhost:8080"}
        ],
        "model_mappings": [
            {"model_id": "gpt-5.4", "backend_ids": ["llama-server-1"]},
            {"model_id": "claude-opus-4.6", "backend_ids": ["llama-server-1"]}
        ]
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
        
    config = load_config(config_file)
    assert isinstance(config, Config)
    assert len(config.backends) == 1
    assert config.backends[0].id == "llama-server-1"
    assert config.backends[0].url == "http://localhost:8080"
    
    assert len(config.model_mappings) == 2
    assert config.model_mappings[0].model_id == "gpt-5.4"
    assert config.model_mappings[0].backend_ids == ["llama-server-1"]
    assert config.model_mappings[1].model_id == "claude-opus-4.6"
    assert config.model_mappings[1].backend_ids == ["llama-server-1"]

def test_invalid_config_schema(tmp_path: Path):
    config_data = {
        "backends": [
            {"id": "backend1"} # Missing URL
        ]
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
        
    with pytest.raises(ValidationError):
        load_config(config_file)

def test_config_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_config(Path("non_existent_config.yaml"))
