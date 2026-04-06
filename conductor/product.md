# Initial Concept
A multi-API-endpoint proxy that allows me to take a bunch of `llama-server` instances and map them into one single OpenAI + Anthropic compatible endpoint with configurable model IDs, plus a dashboard that allows viewing real-time activity and collecting statistics, both real-time and aggregate, on token usage.

# Product Guide

## Project Vision
A high-performance, resilient multi-API-endpoint proxy designed for self-hosters and home lab enthusiasts. This tool seamlessly aggregates multiple `llama-server` instances into a single, unified API compatible with OpenAI and Anthropic specifications. It empowers users with granular control over model IDs and provides a sophisticated dashboard for real-time observability and comprehensive token usage analytics.

## Target Audience
- **Self-hosters & Home Lab Users:** Individuals managing their own AI infrastructure who need a robust way to unify and monitor multiple model servers.

## Core Goals
- **Performance and Low Latency:** Ensuring the proxy introduces minimal overhead, maintaining the speed of the underlying inference engines.
- **Resilience and Failover Support:** Automatically managing multiple backends to provide a reliable endpoint even if individual servers go offline.
- **Observability and Statistics Monitoring:** Providing deep insights into system activity and resource consumption through real-time and aggregate metrics.

## Key Features
- **Unified API Endpoint:** Multi-backend aggregation with full OpenAI and Anthropic compatibility.
- **Configurable Model Mapping:** Flexible mapping of backend instances to specific model IDs.
- **Interactive Dashboard:** Real-time activity feed and statistical visualizations.
- **Token Analytics:** Detailed tracking of token usage across models and timeframes.
- **Metrics Exporting:** Support for detailed activity logging and metrics integration with external monitoring tools.

## Technical Strategy
- **Deployment:** Primarily targeted for bare metal or native binary execution for maximum performance and direct resource access.
- **Efficiency:** Focused on a lightweight architecture to minimize latency and resource footprint.
