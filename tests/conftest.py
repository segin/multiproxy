import os
import pytest
from app.logger import init_db

@pytest.fixture(scope="session", autouse=True)
def test_db_env(tmp_path_factory):
    """
    Enforce a test-specific database path for the entire test session.
    This prevents tests from writing to the production logs.db.
    """
    tmp_dir = tmp_path_factory.mktemp("db")
    test_db_path = str(tmp_dir / "test_logs.db")
    
    # Force the logger to use the test database
    init_db(test_db_path)
    
    yield
    
    # We don't necessarily need to restore the path here because 
    # the process will exit after tests, but let's be clean.
    # Note: app.logger._DEFAULT_DB_PATH is calculated at module import.
