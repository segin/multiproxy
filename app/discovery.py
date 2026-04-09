import httpx
import logging
from typing import Dict, Optional
from app.config import Config

_backend_limits: Dict[str, int] = {}
logger = logging.getLogger(__name__)

async def discover_backend_limits(config: Config):
    """
    Query the /props endpoint of each configured backend to discover token limits.
    For llama.cpp server, /props returns JSON containing default_generation_settings.n_ctx.
    """
    global _backend_limits
    _backend_limits.clear()
    
    async with httpx.AsyncClient() as client:
        for backend in config.backends:
            # If backend URL has /v1, strip it to get to /props at the root
            base_url = backend.url.rstrip("/")
            if base_url.endswith("/v1"):
                base_url = base_url[:-3]
            
            props_url = f"{base_url}/props"
            try:
                response = await client.get(props_url, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                
                # Try to extract n_ctx
                if "default_generation_settings" in data and "n_ctx" in data["default_generation_settings"]:
                    _backend_limits[backend.id] = data["default_generation_settings"]["n_ctx"]
                else:
                    logger.warning(f"Could not find n_ctx in /props for backend {backend.id}")
            except Exception as e:
                logger.warning(f"Failed to fetch limits from backend {backend.id}: {e}")

def get_backend_limit(backend_id: str) -> Optional[int]:
    return _backend_limits.get(backend_id)
