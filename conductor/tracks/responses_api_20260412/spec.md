# Track Specification: Responses API Support

## Overview
This track implements support for OpenAI's new `/v1/responses` endpoint alongside the existing `/v1/chat/completions` endpoint in MultiProxy. It involves handling new schemas (`instructions`, `input`, etc.), correctly parsing streamed arrays (`output` instead of `choices`), extracting token timings properly from the backend response, and logging this traffic seamlessly to the existing dashboard structure.

## Objectives
- Create Pydantic models for the new Responses API request and response bodies.
- Implement a new `/v1/responses` endpoint in `app/main.py` that forwards requests to configured backends.
- Ensure the backend discovery features (token limit checking, fallbacks) work properly with Responses.
- Implement SSE streaming logic that parses the new response format (e.g. `output` chunks) and correctly accumulates tokens.
- Add logging to capture metrics and duration for the new endpoint exactly as is done for chat completions.

## Scope
- **Schemas:** `app/schemas.py`
- **Main App:** `app/main.py` (routing, token accumulation, fallback checking)
- **Testing:** `tests/test_responses_api.py`

## Technical Requirements
- FastAPI
- Pydantic
- httpx (async HTTP requests)

## Acceptance Criteria
- `/v1/responses` handles synchronous requests correctly.
- `/v1/responses` handles streamed requests correctly.
- Token counts and performance metrics appear correctly in the proxy's dashboard.
- Extensive unit tests cover edge cases (timeouts, connection drops, empty responses).
