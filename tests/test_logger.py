from app.logger import log_request, get_logs, clear_logs
from app.schemas import UsageInfo

def test_logger_records_event():
    clear_logs()
    
    usage = UsageInfo(prompt_tokens=10, completion_tokens=20, total_tokens=30)
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
    assert log_entry["usage"].total_tokens == 30
