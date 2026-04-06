# Track Specification: Core Proxy Functionality

## Overview
This track focuses on building the core of the multi-API-endpoint proxy. The goal is to create a high-performance Python-based proxy that can aggregate multiple `llama-server` instances into a single OpenAI-compatible endpoint with flexible model mapping and streaming support.

## Objectives
- Implement a robust configuration management system using a single YAML/JSON file.
- Develop the core request routing and model mapping logic.
- Create an OpenAI-compatible API endpoint using FastAPI.
- Ensure full support for streaming responses from multiple backends.
- Integrate SQLite for tracking real-time and aggregate token usage metrics.

## Scope
- **Backend:** FastAPI for API and proxy logic.
- **Concurrency:** Asynchronous request handling with `httpx` or similar.
- **Mapping:** Configuration-driven mapping of model IDs to specific backend URLs.
- **Observability:** Token counting and logging to a local SQLite database.

## Technical Requirements
- Python 3.10+
- FastAPI
- SQLite
- httpx (for async HTTP requests)
- YAML/JSON configuration support

## Acceptance Criteria
- Proxy successfully routes requests to the correct backend based on model ID.
- Streaming responses work seamlessly with OpenAI-compatible clients.
- Configuration can be easily updated via a single file.
- Token usage is accurately tracked and stored in the SQLite database.
- Latency introduced by the proxy is minimal.
