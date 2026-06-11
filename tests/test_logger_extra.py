import logging
import sys
import pytest
from app.logger import DBLogHandler, init_db, get_system_logs, clear_logs


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    init_db(str(tmp_path / "logger_extra.db"))
    yield


def test_db_log_handler_records_traceback():
    handler = DBLogHandler()
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord("audit-test", logging.ERROR, __file__, 1, "it failed", None, sys.exc_info())
    handler.emit(record)

    logs = get_system_logs()
    assert logs[0]["message"].startswith("it failed")
    assert "ValueError: boom" in logs[0]["traceback"]


def test_db_log_handler_handles_emit_failure(capsys):
    handler = DBLogHandler()
    # Mismatched format args make self.format() raise inside emit()
    record = logging.LogRecord("audit-test", logging.INFO, __file__, 1, "bad %s %s", ("only-one",), None)
    handler.emit(record)  # must not raise
    assert get_system_logs() == [] or all(l["message"] != "bad %s %s" for l in get_system_logs())


def test_clear_logs_empties_system_logs():
    handler = DBLogHandler()
    handler.emit(logging.LogRecord("audit-test", logging.INFO, __file__, 1, "hello", None, None))
    assert len(get_system_logs()) == 1
    clear_logs()
    assert get_system_logs() == []
