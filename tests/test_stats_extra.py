import pytest
from app.logger import init_db, log_request, clear_logs
from app.schemas import UsageInfo
from app.stats import get_aggregate_stats, get_time_series_stats


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    init_db(str(tmp_path / "stats_extra.db"))
    yield


def test_aggregate_stats_with_hours_filter():
    log_request("m1", "http://b", 200, 100.0, UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15))
    stats = get_aggregate_stats(hours=1)
    assert stats["total_requests"] == 1
    assert stats["total_tokens"] == 15


def test_aggregate_stats_empty_db_normalizes_all_fields():
    clear_logs()
    stats = get_aggregate_stats()
    assert stats["total_requests"] == 0
    assert stats["total_tokens"] == 0
    assert stats["total_compute_burn"] == 0
    assert stats["avg_ttft_ms"] == 0.0
    assert stats["avg_tokens_per_second"] == 0.0


def test_time_series_invalid_period_returns_empty():
    assert get_time_series_stats("decade") == []
