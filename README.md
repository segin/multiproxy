# MultiProxy

A high-performance, resilient multi-backend proxy and HTMX dashboard for local LLM inference. MultiProxy seamlessly aggregates multiple `llama-server` (llama.cpp) instances or other compatible backends into unified, single API endpoints with full compatibility for both **OpenAI** and **Anthropic** specifications.

## Features

- **Multi-Protocol Support**: Fully supports OpenAI's `/v1/chat/completions` and `/v1/responses` endpoints, as well as Anthropic's `/v1/messages` and `/v1/messages/count_tokens` endpoints.
- **Direct Backend Routing**: Forwards requests directly to the native endpoints of your configured backend servers.
- **Token Analytics & Dashboard**: Includes an interactive, HTMX-powered web dashboard that tracks real-time activity, tokens per second, time-to-first-token (TTFT), and aggregate usage metrics across all models and timeframes.
- **Configurable Model Mapping**: Map requested model IDs (like `gpt-4-turbo` or `claude-3-opus`) to specific backend servers for load balancing and granular control.
- **Default Model Fallback**: Automatically reroute requests for unknown or unmapped models to a designated default backend.
- **Context Limit Discovery**: Automatically queries backend servers on startup to discover context limits and proactively rejects requests that exceed the available context window.
- **Robust Error Handling**: Implements graceful failovers, translates backend errors, and safely handles Server-Sent Events (SSE) streaming interruptions.

## Configuration

MultiProxy uses a simple `config.yaml` file to manage backend routing. For full details on how to configure your backends, model mappings, and default routing behaviors, please see the [Configuration Guide](CONFIGURATION.md).

## Getting Started

1. Ensure you have Python 3.14+ installed.
2. Activate your virtual environment and install requirements (if any).
3. Create your `config.yaml` based on the configuration guide.
4. Start the proxy and dashboard using the provided script:
   ```bash
   ./start.sh
   ```
5. The proxy API will be available on port `8001` and the interactive dashboard on port `8080`.

## License

This project is licensed under the MIT License.
