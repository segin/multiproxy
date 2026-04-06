# Track Specification: Statistics API and Interactive Dashboard

## Overview
This track focuses on building a dedicated Statistics API and an interactive web dashboard running on a separate port from the core proxy. The dashboard will use HTMX and Jinja2 templates, served by FastAPI, to provide a "Utilitarian / Industrial" interface. It will visualize token usage, backend health, and real-time request logging directly from the `logs.db` SQLite database.

## Objectives
- Create a secondary FastAPI application that runs concurrently with or alongside the main proxy.
- Ensure the dashboard runs on a distinct, configurable port (e.g., 8080).
- Provide read-only data access layers for querying the proxy's SQLite database efficiently.
- Build HTMX-powered components for:
  - High-level summaries (total tokens, average latency, request counts).
  - Log-centric activity views (filterable, paginated tables).
  - Visual-first metrics (basic charts or dynamic data updates).
- Enforce the chosen utilitarian, high-contrast visual design principles.

## Scope
- **Backend:** A new FastAPI instance (`app/dashboard.py`) and Jinja2 for template rendering.
- **Frontend:** HTMX embedded in HTML templates with plain CSS.
- **Data:** Read operations only on the existing `logs.db`.

## Technical Requirements
- Python 3.10+
- FastAPI, Jinja2, HTMX (via CDN or local static file)
- SQLite (`sqlite3`)

## Acceptance Criteria
- Dashboard runs on a separate port and is accessible via a web browser.
- Real-time and historical stats are accurately retrieved from the database.
- The interface updates dynamically using HTMX without full page reloads.
- The styling aligns with the "Utilitarian / Industrial" product guidelines.