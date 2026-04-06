import random
from app.config import Config, Backend

class ModelNotFoundError(Exception):
    pass

class NoBackendsAvailableError(Exception):
    pass

def get_backend(model_id: str, config: Config) -> Backend:
    # Find mapping for the model
    mapping = next((m for m in config.model_mappings if m.model_id == model_id), None)
    
    # Fallback to default_model_id if available
    if not mapping and config.default_model_id:
        mapping = next((m for m in config.model_mappings if m.model_id == config.default_model_id), None)
        
    if not mapping:
        raise ModelNotFoundError(f"Model '{model_id}' is not mapped to any backends and no valid default model is configured.")
    
    # Collect all available backends for the mapped backend IDs
    backends = [
        b for b in config.backends if b.id in mapping.backend_ids
    ]
    
    if not backends:
        raise NoBackendsAvailableError(f"No configured backends found for model '{model_id}'.")
    
    # Load balancing via random choice
    return random.choice(backends)

def get_backend_url(model_id: str, config: Config) -> str:
    return get_backend(model_id, config).url
