# Architecture Overview
This document serves as a critical, living template designed to equip agents with a rapid and comprehensive understanding of the codebase's architecture, enabling efficient navigation and effective contribution from day one.

## 1. Project Structure

[Project Root]/
├── app/                  # Main source code for backend proxy and dashboard
│   ├── templates/        # HTML templates for the dashboard (HTMX, Jinja2)
│   ├── config.py         # Configuration loading (config.yaml)
│   ├── dashboard.py      # Dashboard FastAPI application (port 8080)
│   ├── discovery.py      # Backend limit discovery logic
│   ├── logger.py         # SQLite database logging and connection management
│   ├── main.py           # Core proxy FastAPI application (port 8001)
│   ├── mapping.py        # Model to backend mapping logic
│   ├── schemas.py        # Pydantic schemas (OpenAI/Anthropic APIs)
│   ├── stats.py          # Dashboard analytics and metrics aggregation
│   └── tokens.py         # Token counting logic (tiktoken)
├── conductor/            # Project management and track specifications
├── tests/                # Pytest unit and integration tests
├── config.yaml.sample    # Sample configuration file
├── CONFIGURATION.md      # Configuration guide
├── README.md             # Project overview
├── start.sh              # Startup script for proxy and dashboard
├── AGENTS.md             # Guidelines for AI coding agents
└── ARCHITECTURE.md       # This document

## 2. High-Level System Diagram

[Client (OpenAI/Anthropic SDK)] <--> [Proxy (app/main.py, port 8001)] <--> [Backend Servers (e.g., llama.cpp)]
                                      |
                                      v
                                 [SQLite DB (logs.db)]
                                      ^
                                      |
[User Browser] <-----------------> [Dashboard (app/dashboard.py, port 8080)]

## 3. Core Components

### 3.1. Proxy Service (app/main.py)
Name: MultiProxy API
Description: Aggregates multiple backend models into an OpenAI/Anthropic compatible API. Handles request routing, SSE streaming, and error handling.
Technologies: Python, FastAPI, httpx, tiktoken
Deployment: Native Python execution (port 8001)

### 3.2. Dashboard Service (app/dashboard.py)
Name: MultiProxy Dashboard
Description: Provides an interactive UI for real-time and historical token analytics, request logs, and system logs.
Technologies: Python, FastAPI, Jinja2, HTMX, Chart.js
Deployment: Native Python execution (port 8080)

## 4. Data Stores

### 4.1. SQLite Database
Name: logs.db
Type: SQLite
Purpose: Stores all API request logs (metadata, token usage, latency) and internal system logs.
Key Schemas/Collections: logs, system_logs

## 5. External Integrations / APIs

Service Name 1: Backend Inference Servers (e.g., llama-server, vLLM)
Purpose: Actual execution of LLM inference.
Integration Method: HTTP API (OpenAI/Anthropic compatible formats)

## 6. Deployment & Infrastructure

Deployment: Bare metal or native binary execution.
Startup: Managed via `./start.sh` which runs both `uvicorn` instances.

## 7. Security Considerations

Data Encryption: Typically deployed behind a reverse proxy (e.g., Nginx, Caddy) for TLS termination.
Network: Proxy exposes 8001, Dashboard exposes 8080 locally.

## 8. Development & Testing Environment

Local Setup Instructions: Run `python3 -m venv venv`, `source venv/bin/activate`, `pip install -r requirements.txt`.
Testing Frameworks: Pytest, pytest-asyncio, pytest-cov.
Code Quality Tools: Standard Python linters/formatters as per user configuration.

## 9. Future Considerations / Roadmap

- Further modularization of `app/main.py` into separate protocol handlers (OpenAI vs Anthropic).

## 10. Project Identification

Project Name: MultiProxy
Repository URL: https://github.com/segin/multiproxy
