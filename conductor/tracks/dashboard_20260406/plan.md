# Implementation Plan: Statistics API and Interactive Dashboard

## Phase 1: Dashboard Application Setup
- [x] Task: Initialize Dashboard App 42d0647
    - [ ] Create a new FastAPI application specifically for the dashboard (`app/dashboard.py`).
    - [ ] Configure the application to serve Jinja2 templates.
    - [ ] Create a startup script or configuration that allows running the proxy and the dashboard on separate ports simultaneously.
    - [ ] Write unit tests verifying the dashboard app initializes correctly.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Dashboard Application Setup' (Protocol in workflow.md) [checkpoint: 06d723b]

## Phase 2: Statistics API and Data Access
- [x] Task: SQLite Data Access Layer 85cae5d
    - [ ] Implement database queries for aggregate metrics (total tokens, average duration, request counts per model/backend).
    - [ ] Implement queries for recent logs with pagination support.
    - [ ] Write unit tests for these data access functions.
- [x] Task: Internal API Endpoints d249e2b
    - [ ] Create FastAPI endpoints in the dashboard app that return JSON or HTML fragments (for HTMX).
    - [ ] Test the internal API endpoints to ensure correct data formatting.
- [~] Task: Conductor - User Manual Verification 'Phase 2: Statistics API and Data Access' (Protocol in workflow.md) [checkpoint: ]

## Phase 3: HTMX Frontend Implementation
- [ ] Task: Base Template and Styling
    - [ ] Create the core `base.html` Jinja2 template.
    - [ ] Add CSS styling adhering to the "Utilitarian / Industrial" guidelines (high contrast, clear typography).
- [ ] Task: High-Level Summary Widgets
    - [ ] Build HTMX components to display total token consumption and system health metrics.
    - [ ] Integrate these widgets into the main dashboard view.
- [ ] Task: Log-Centric Activity Views
    - [ ] Build a filterable, paginated HTML table for detailed request logs.
    - [ ] Use HTMX to allow pagination and filtering without full page reloads.
## Phase 4: Backend Token Limit Discovery
- [x] Task: Backend Context Size Discovery 19ded86
    - [ ] Implement an async startup/refresh task to query `/props` on each configured backend.
    - [ ] Cache the discovered `n_ctx` token limit for each model/backend.
    - [ ] Update the `chat_completions` endpoint to proactively reject requests that exceed this limit with a 400 error.
- [x] Task: Model Discovery Endpoint 19ded86
    - [ ] Implement a `GET /v1/models` endpoint that returns all configured models and their discovered token limits.
    - [ ] Write unit tests for the discovery endpoints and validation logic.
- [~] Task: Conductor - User Manual Verification 'Phase 4: Backend Token Limit Discovery' (Protocol in workflow.md) [checkpoint: ]