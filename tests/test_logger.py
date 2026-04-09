import os
import sqlite3
import pytest
from app.logger import log_request, get_logs, clear_logs, init_db
from app.schemas import UsageInfo

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_path = tmp_path / "test_logs_local.db"
    init_db(str(db_path))
    yield

def test_logger_records_event_to_sqlite():
    clear_logs()
    
    usage = UsageInfo(
        prompt_tokens=10, 
        completion_tokens=20, 
        total_tokens=30,
        prompt_tokens_details={"cached_tokens": 5}
    )
    log_request(
        model_id="gpt-3.5-turbo",
        backend_url="http://fake-backend:8080",
        status_code=200,
        duration_ms=150.5,
        usage=usage
    )
    
    logs = get_logs()
    assert len(logs) == 1
    
    log_entry = logs[0]
    assert log_entry["model_id"] == "gpt-3.5-turbo"
    assert log_entry["backend_url"] == "http://fake-backend:8080"
    assert log_entry["status_code"] == 200
    assert log_entry["duration_ms"] == 150.5
    assert log_entry["prompt_tokens"] == 10
    assert log_entry["completion_tokens"] == 20
    assert log_entry["total_tokens"] == 30
    assert log_entry["prompt_cached_tokens"] == 5
