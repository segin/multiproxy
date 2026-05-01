from pathlib import Path
from typing import List
import yaml
from pydantic import BaseModel, HttpUrl

class Backend(BaseModel):
    id: str
    url: str
    context_size: int | None = None

class ModelMapping(BaseModel):
    model_id: str
    backend_ids: List[str]

class Config(BaseModel):
    backends: List[Backend]
    model_mappings: List[ModelMapping]
    default_model_id: str | None = None
    default_embedding_model_id: str | None = None

def load_config(file_path: str | Path) -> Config:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    
    with open(path, "r") as f:
        data = yaml.safe_load(f)
        
    return Config(**data)
