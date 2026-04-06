from typing import List, Dict, Any
from app.schemas import UsageInfo
import time

# In-memory store for logs (will be replaced by SQLite in Phase 3.2)
_logs: List[Dict[str, Any]] = []

def log_request(
    model_id: str,
    backend_url: str,
    status_code: int,
    duration_ms: float,
    usage: UsageInfo | None = None
):
    log_entry = {
        "timestamp": time.time(),
        "model_id": model_id,
        "backend_url": backend_url,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "usage": usage
    }
    _logs.append(log_entry)

def get_logs() -> List[Dict[str, Any]]:
    return _logs

def clear_logs():
    _logs.clear()