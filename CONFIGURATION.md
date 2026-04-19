# MultiProxy Configuration Guide

MultiProxy uses a simple `config.yaml` file located in the root directory of the project to manage backends, model mappings, and default routing behaviors.

## Overview of `config.yaml`

The configuration file consists of three main sections:
1.  **`backends`**: A list of your actual backend inference servers (e.g., `llama-server`, `vLLM`, or other OpenAI/Anthropic compatible endpoints).
2.  **`model_mappings`**: A list defining how specific model names requested by clients map to your configured backends.
3.  **`default_model_id`** (Optional): A fallback model ID used when a client requests a model that isn't explicitly defined in your mappings.

---

## 1. Configuring Backends

The `backends` section defines the physical servers that will process your requests. Each backend requires an `id` and a `url`.

```yaml
backends:
  - id: installation-00
    url: http://installation-00:8080
  - id: fallback-gpu
    url: http://192.168.1.100:8080
```

*   **`id`**: A unique string identifier for this backend. You will use this ID in the `model_mappings` section.
*   **`url`**: The base URL of the backend server. MultiProxy automatically appends the correct API paths (like `/v1/chat/completions` or `/v1/messages`) when forwarding requests, so you only need to provide the root or base URL.

## 2. Configuring Model Mappings

The `model_mappings` section tells MultiProxy which backend(s) to use when a client requests a specific model name.

```yaml
model_mappings:
  - model_id: qwen3.6-35b-a3b
    backend_ids:
      - installation-00
  - model_id: gpt-4-turbo
    backend_ids:
      - installation-00
      - fallback-gpu
```

*   **`model_id`**: The exact model string your client (like Claude Code, OpenCode, or an OpenAI SDK) will send in its request.
*   **`backend_ids`**: A list of backend IDs (defined in the `backends` section) that are capable of serving this model.
    *   *Load Balancing:* If you provide multiple backend IDs for a single model (like `gpt-4-turbo` in the example above), MultiProxy will automatically load-balance requests across them.

## 3. The Default Model Fallback

Often, clients or IDE plugins might request a model name that you haven't explicitly mapped (e.g., they hardcode `gpt-3.5-turbo` or `claude-3-opus-20240229`). Instead of outright failing, you can configure a default model fallback.

```yaml
default_model_id: qwen3.6-35b-a3b
```

If a client requests an unmapped model, MultiProxy will intercept the request and seamlessly reroute it to the backends mapped to your `default_model_id`. The client remains unaware, and your backend handles the request normally.

---

## Full Example `config.yaml`

```yaml
backends:
  - id: main-server
    url: http://localhost:8080
  - id: secondary-server
    url: http://192.168.1.50:8080

default_model_id: qwen3.6-35b-a3b

model_mappings:
  - model_id: qwen3.6-35b-a3b
    backend_ids:
      - main-server
      
  - model_id: llama-3-70b
    backend_ids:
      - secondary-server
      
  - model_id: fast-model
    backend_ids:
      - main-server
      - secondary-server
```

## Reloading Configuration
Currently, MultiProxy loads `config.yaml` on startup. If you make changes to this file, you must restart the MultiProxy service (e.g., by stopping the process and running `./start.sh` again) for the changes to take effect.