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
- [x] Task: Internal API Endpoints d249e2b
- [x] Task: Time-based Granular Statistics abfc1f4
    - [ ] Implement database queries for aggregate metrics (total tokens, average duration, request counts per model/backend).
    - [ ] Implement queries for recent logs with pagination support.
    - [ ] Support time-period filtering (hourly, daily, monthly).
    - [ ] Write unit tests for these data access functions.
- [~] Task: Conductor - User Manual Verification 'Phase 2: Statistics API and Data Access' (Protocol in workflow.md) [checkpoint: ]

## Phase 3: HTMX Frontend Implementation
- [x] Task: Base Template and Styling 0866c9a
- [x] Task: High-Level Summary Widgets ff477c1
- [x] Task: Log-Centric Activity Views ff477c1
- [x] Task: Time-period Selector UI abfc1f4
    - [ ] Build HTMX components to display total token consumption and system health metrics.
    - [ ] Integrate these widgets into the main dashboard view.
    - [ ] Implement UI controls to switch between different statistics timeframes.
- [~] Task: Conductor - User Manual Verification 'Phase 3: HTMX Frontend Implementation' (Protocol in workflow.md) [checkpoint: ]

## Phase 5: Advanced Historical Analytics
- [x] Task: Time-series Data Aggregation d7de8fb
- [x] Task: Interactive Charting UI d7de8fb
    - [ ] Implement database queries to group usage by hour (for 24h), day (for 30d), and month (for 1y).
    - [ ] Create API endpoints to return this time-series data in JSON format.
    - [ ] Integrate a charting library (e.g., Chart.js) into the dashboard.
    - [ ] Create an "Advanced View" page (`advanced.html`) with interactive bar/line charts.
    - [ ] Add a navigation toggle to "Summon" the advanced view from the main dashboard using HTMX.
    - [ ] Write unit tests for the aggregation logic.
- [~] Task: Conductor - User Manual Verification 'Phase 5: Advanced Historical Analytics' (Protocol in workflow.md) [checkpoint: ]