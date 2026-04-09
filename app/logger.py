import sqlite3
import time
import os
import logging
from typing import List, Dict, Any, Optional
from app.schemas import UsageInfo

_DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs.db")
_DB_PATH = _DEFAULT_DB_PATH

def init_db(db_path: str = _DEFAULT_DB_PATH):
    global _DB_PATH
    _DB_PATH = db_path
    
    with sqlite3.connect(_DB_PATH) as conn:
        cursor = conn.cursor()
        # API Request Logs
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
                total_tokens INTEGER,
                prompt_cached_tokens INTEGER,
                cache_creation_input_tokens INTEGER,
                cache_read_input_tokens INTEGER,
                error_message TEXT
            )
        """)
        # System/Internal Logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                level TEXT NOT NULL,
                name TEXT NOT NULL,
                message TEXT NOT NULL,
                traceback TEXT
            )
        """)
        # Add columns if they don't exist
        for col in ["prompt_cached_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "error_message"]:
            try:
                cursor.execute(f"ALTER TABLE logs ADD COLUMN {col} INTEGER")
            except sqlite3.OperationalError:
                pass 
        conn.commit()

class DBLogHandler(logging.Handler):
    def emit(self, record):
        try:
            timestamp = time.time()
            level = record.levelname
            name = record.name
            message = self.format(record)
            traceback = None
            if record.exc_info:
                import traceback as tb
                traceback = "".join(tb.format_exception(*record.exc_info))
            
            with sqlite3.connect(_DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO system_logs (timestamp, level, name, message, traceback) VALUES (?, ?, ?, ?, ?)",
                    (timestamp, level, name, message, traceback)
                )
                conn.commit()
        except Exception:
            self.handleError(record)

def setup_logging():
    # Configure root logger to include timestamps in console
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )
    # Add our database handler
    db_handler = DBLogHandler()
    db_handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(db_handler)

def log_request(
    model_id: str,
    backend_url: str,
    status_code: int,
    duration_ms: float,
    usage: Optional[UsageInfo] = None,
    error_message: Optional[str] = None
):
    prompt_cached = usage.prompt_tokens_details.get("cached_tokens") if usage and usage.prompt_tokens_details else None
    cache_creation = usage.cache_creation_input_tokens if usage else None
    cache_read = usage.cache_read_input_tokens if usage else None

    with sqlite3.connect(_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO logs (
                timestamp, model_id, backend_url, status_code, duration_ms, 
                prompt_tokens, completion_tokens, total_tokens, 
                prompt_cached_tokens, cache_creation_input_tokens, cache_read_input_tokens,
                error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            time.time(),
            model_id,
            backend_url,
            status_code,
            duration_ms,
            usage.prompt_tokens if usage else None,
            usage.completion_tokens if usage else None,
            usage.total_tokens if usage else None,
            prompt_cached,
            cache_creation,
            cache_read,
            error_message
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

def get_system_logs(limit: int = 50) -> List[Dict[str, Any]]:
    with sqlite3.connect(_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

def clear_logs():
    with sqlite3.connect(_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM logs")
        cursor.execute("DELETE FROM system_logs")
        conn.commit()

# Auto-initialize with default path
init_db()
