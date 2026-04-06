import random
from app.config import Config

class ModelNotFoundError(Exception):
    pass

class NoBackendsAvailableError(Exception):
    pass

def get_backend_url(model_id: str, config: Config) -> str:
    # Find mapping for the model
    mapping = next((m for m in config.model_mappings if m.model_id == model_id), None)
    if not mapping:
        raise ModelNotFoundError(f"Model '{model_id}' is not mapped to any backends.")
    
    # Collect all available backend URLs for the mapped backend IDs
    backend_urls = [
        b.url for b in config.backends if b.id in mapping.backend_ids
    ]
    
    if not backend_urls:
        raise NoBackendsAvailableError(f"No configured backends found for model '{model_id}'.")
    
    # Load balancing via random choice
    return random.choice(backend_urls)
