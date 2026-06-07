# AGENTS.md

## Setup commands
- Start dev server: `./start.sh` (Runs proxy on 8001 and dashboard on 8080)
- Run tests: `PYTHONPATH=. source venv/bin/activate && pytest`
- Check coverage: `PYTHONPATH=. source venv/bin/activate && pytest --cov=app --cov-report=term-missing`

## Code style
- Python 3.10+, FastAPI, SQLite, HTMX, Jinja2, Chart.js.
- Strict Schema Passthrough: Must use Pydantic `ConfigDict(extra="allow")` to prevent stripping unknown JSON fields (crucial for tools, tool_choice, tool_calls).
- Database: ALWAYS use the custom `get_db_connection` context manager with `finally: conn.close()` to prevent SQLite file descriptor exhaustion.
- Streaming Error Handling: Raising HTTPExceptions during FastAPI `StreamingResponse` causes ASGI crashes; errors must be yielded as Server-Sent Event (SSE) data chunks.
- Token Metrics: The proxy forcefully injects `stream_options.include_usage = True` to guarantee exact ground-truth token counts from the backend.
- Analytics: Calculate `tokens_per_second` strictly excluding Time-To-First-Token (TTFT).

## Testing instructions
- TDD with >95% test coverage required.
- Enforce isolated temporary `test_logs.db` for pytest runs to prevent polluting production metrics (managed in `tests/conftest.py`).
- Always run tests before committing.

## PR instructions
- Commit after every completed task.
