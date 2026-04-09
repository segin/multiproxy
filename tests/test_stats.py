import pytest
import sqlite3
from app.logger import init_db, log_request, clear_logs
from app.schemas import UsageInfo
from app.stats import get_aggregate_stats, get_recent_logs, get_time_series_stats

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_path = tmp_path / "test_stats_local.db"
    init_db(str(db_path))
    clear_logs()
    
    # Insert some dummy data
    log_request("model-a", "http://back1", 200, 100.0, UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15))
    log_request("model-b", "http://back2", 200, 200.0, UsageInfo(prompt_tokens=20, completion_tokens=10, total_tokens=30))
    log_request("model-a", "http://back1", 500, 50.0, UsageInfo(prompt_tokens=5, completion_tokens=0, total_tokens=5))
    
    yield

def test_get_aggregate_stats():
    stats = get_aggregate_stats()
    assert stats["total_requests"] == 3
    assert stats["total_input_tokens"] == 35 # 10 + 20 + 5
    assert stats["total_output_tokens"] == 15 # 5 + 10 + 0
    assert stats["total_tokens"] == 50
    # avg duration = (100+200+50)/3 = 116.66
    assert round(stats["avg_duration_ms"], 2) == 116.67
    
    # Check per model requests
    models = stats["model_requests"]
    assert len(models) == 2
    assert any(m["model_id"] == "model-a" and m["count"] == 2 for m in models)
    assert any(m["model_id"] == "model-b" and m["count"] == 1 for m in models)

def test_get_recent_logs_pagination():
    logs = get_recent_logs(limit=2, offset=0)
    assert len(logs) == 2
    # They should be sorted by timestamp DESC
    assert logs[0]["status_code"] == 500 # The last inserted
    
    logs_page2 = get_recent_logs(limit=2, offset=2)
    assert len(logs_page2) == 1
    assert logs_page2[0]["status_code"] == 200 # The first inserted

def test_get_aggregate_stats_empty():
    clear_logs()
    stats = get_aggregate_stats()
    assert stats["total_requests"] == 0
    assert stats["total_tokens"] == 0
    assert stats["avg_duration_ms"] == 0.0
    assert len(stats["model_requests"]) == 0

def test_get_time_series_stats():
    # Hour aggregation
    stats = get_time_series_stats("hour")
    assert len(stats) >= 1
    assert "label" in stats[0]
    assert "tokens" in stats[0]
    
    # Day aggregation
    stats = get_time_series_stats("day")
    assert len(stats) >= 1
    
    # Month aggregation
    stats = get_time_series_stats("month")
    assert len(stats) >= 1
    
    # Invalid period
    assert get_time_series_stats("invalid") == []
