# Implementation Plan: Responses API Support

## Phase 1: Schemas and Basic Routing
- [x] Task: Response API Schemas
    - [ ] Create Pydantic models for `/v1/responses` requests (`instructions`, `input`, `tools`, etc.).
    - [ ] Create Pydantic models for `/v1/responses` responses (`output` array, etc.).
- [x] Task: Non-Streaming Endpoint Implementation
    - [ ] Add the `@app.post("/v1/responses")` route in `app/main.py`.
    - [ ] Forward the request to the chosen backend (or fallback).
    - [ ] Handle model limit validation and fallback logic similarly to `/v1/chat/completions`.
    - [ ] Write unit tests for non-streaming requests.
- [~] Task: Conductor - User Manual Verification 'Phase 1: Schemas and Basic Routing' (Protocol in workflow.md) [checkpoint: ]

## Phase 2: Streaming and Observability
- [ ] Task: Streaming Implementation
    - [ ] Build `stream_responses_api` generator.
    - [ ] Parse streamed chunks matching the `v1/responses` structure (e.g., look for `output` instead of `choices`).
    - [ ] Accumulate token usage effectively.
    - [ ] Inject `stream_options.include_usage` if necessary for backend compliance.
    - [ ] Write unit tests for streaming behavior.
- [ ] Task: Observability Integration
    - [ ] Ensure `log_request` receives correct metadata (`ttft_ms`, `tokens_per_second`, token counts) for the Responses API.
    - [ ] Verify logs correctly insert into SQLite and populate the dashboard.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Streaming and Observability' (Protocol in workflow.md) [checkpoint: ]
