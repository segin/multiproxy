import sqlite3
import time
from typing import List, Dict, Any
from app.schemas import UsageInfo

_DB_PATH = "logs.db"

def init_db(db_path: str = "logs.db"):
    global _DB_PATH
    _DB_PATH = db_path
    
    with sqlite3.connect(_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                model_id TEXT NOT NULL,
                backend_url TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                duration_ms REAL NOT NULL,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER
            )
        """)
        conn.commit()

def log_request(
    model_id: str,
    backend_url: str,
    status_code: int,
    duration_ms: float,
    usage: UsageInfo | None = None
):
    with sqlite3.connect(_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO logs (
                timestamp, model_id, backend_url, status_code, duration_ms, 
                prompt_tokens, completion_tokens, total_tokens
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            time.time(),
            model_id,
            backend_url,
            status_code,
            duration_ms,
            usage.prompt_tokens if usage else None,
            usage.completion_tokens if usage else None,
            usage.total_tokens if usage else None
        ))
        conn.commit()

def get_logs() -> List[Dict[str, Any]]:
    # Initialize DB if it hasn't been created yet (mainly for safety)
    init_db(_DB_PATH)
    with sqlite3.connect(_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM logs ORDER BY timestamp DESC")
        return [dict(row) for row in cursor.fetchall()]

def clear_logs():
    with sqlite3.connect(_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM logs")
        conn.commit()

# Auto-initialize with default path
init_db()
