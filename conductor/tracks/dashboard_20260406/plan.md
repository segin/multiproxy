# Implementation Plan: Statistics API and Interactive Dashboard

## Phase 1: Dashboard Application Setup
- [x] Task: Initialize Dashboard App 42d0647
    - [ ] Create a new FastAPI application specifically for the dashboard (`app/dashboard.py`).
    - [ ] Configure the application to serve Jinja2 templates.
    - [ ] Create a startup script or configuration that allows running the proxy and the dashboard on separate ports simultaneously.
    - [ ] Write unit tests verifying the dashboard app initializes correctly.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Dashboard Application Setup' (Protocol in workflow.md) [checkpoint: 06d723b]

## Phase 2: Statistics API and Data Access
- [~] Task: SQLite Data Access Layer
    - [ ] Implement database queries for aggregate metrics (total tokens, average duration, request counts per model/backend).
    - [ ] Implement queries for recent logs with pagination support.
    - [ ] Write unit tests for these data access functions.
- [ ] Task: Internal API Endpoints
    - [ ] Create FastAPI endpoints in the dashboard app that return JSON or HTML fragments (for HTMX).
    - [ ] Test the internal API endpoints to ensure correct data formatting.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Statistics API and Data Access' (Protocol in workflow.md) [checkpoint: ]

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
- [ ] Task: Conductor - User Manual Verification 'Phase 3: HTMX Frontend Implementation' (Protocol in workflow.md) [checkpoint: ]