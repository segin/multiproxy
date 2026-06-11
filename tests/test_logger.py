import os
import sqlite3
import pytest
from app.logger import log_request, get_logs, clear_logs, init_db, set_untracked_models
from app.schemas import UsageInfo

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_path = tmp_path / "test_logs_local.db"
    init_db(str(db_path))
    set_untracked_models([])
    yield
    set_untracked_models([])

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
        usage=usage,
        error_message=None,
        ttft_ms=50.0,
        tokens_per_second=100.5
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
    assert log_entry["ttft_ms"] == 50.0
    assert log_entry["tokens_per_second"] == 100.5


def test_logger_skips_untracked_model():
    clear_logs()
    set_untracked_models(["cloud-model"])

    usage = UsageInfo(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    log_request(
        model_id="cloud-model",
        backend_url="http://hosted:443",
        status_code=200,
        duration_ms=100.0,
        usage=usage,
    )

    assert get_logs() == []


def test_logger_records_other_models_when_some_untracked():
    clear_logs()
    set_untracked_models(["cloud-model"])

    usage = UsageInfo(prompt_tokens=1, completion_tokens=2, total_tokens=3)
    log_request("cloud-model", "http://hosted", 200, 10.0, usage)
    log_request("local-model", "http://local", 200, 10.0, usage)

    logs = get_logs()
    assert len(logs) == 1
    assert logs[0]["model_id"] == "local-model"


def test_set_untracked_models_replaces_set():
    clear_logs()
    set_untracked_models(["a", "b"])
    set_untracked_models(["b"])  # replaces, not extends

    usage = UsageInfo(prompt_tokens=1, completion_tokens=2, total_tokens=3)
    log_request("a", "http://x", 200, 10.0, usage)
    log_request("b", "http://x", 200, 10.0, usage)

    logs = get_logs()
    assert {log["model_id"] for log in logs} == {"a"}


def test_set_untracked_models_accepts_none():
    set_untracked_models(["x"])
    set_untracked_models(None)

    clear_logs()
    usage = UsageInfo(prompt_tokens=1, completion_tokens=2, total_tokens=3)
    log_request("x", "http://x", 200, 10.0, usage)
    assert len(get_logs()) == 1
