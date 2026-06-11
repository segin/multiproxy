import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Callable, Optional

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.schemas import ChatCompletionRequest, UsageInfo, ResponsesRequest, AnthropicMessageRequest, EmbeddingRequest
from app.config import Config, load_config
from app.mapping import get_backend, ModelNotFoundError, NoBackendsAvailableError
from app.tokens import count_tokens
from app.logger import log_request, init_db, setup_logging, set_untracked_models
from app.discovery import discover_backend_limits, get_backend_limit

# This will be initialized properly later; for tests we can patch it
current_config = Config(backends=[], model_mappings=[])

_UNSET = object()


def backend_auth_headers(backend, anthropic: bool = False) -> dict:
    """Build outbound auth headers for a backend.

    Why: backends may be hosted services (OpenAI, Anthropic, OpenRouter, etc.)
    that require an API key. When `backend.api_key` is unset, preserve the
    pre-existing behavior — no Authorization for OpenAI-style endpoints, and
    the historical `sk-dummy` placeholder for Anthropic-style endpoints (which
    llama.cpp tolerates).
    """
    if anthropic:
        return {
            "anthropic-version": "2023-06-01",
            "x-api-key": backend.api_key or "sk-dummy",
        }
    if backend.api_key:
        return {"Authorization": f"Bearer {backend.api_key}"}
    return {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global current_config
    setup_logging()
    init_db()
    try:
        current_config = load_config("config.yaml")
    except FileNotFoundError:
        print("Warning: config.yaml not found. Using empty configuration.")
    set_untracked_models(current_config.untracked_models)
    await discover_backend_limits(current_config)
    yield

app = FastAPI(title="MultiProxy", lifespan=lifespan)


def _resolve_backend(model: str, start_time: float, background_tasks: Optional[BackgroundTasks] = None, default_model_override=_UNSET):
    """Resolve the backend and effective model id for a request, translating
    mapping errors into HTTP errors (and logging them when a task queue is given)."""
    kwargs = {}
    fallback_id = current_config.default_model_id
    if default_model_override is not _UNSET:
        kwargs["default_model_override"] = default_model_override
        fallback_id = default_model_override
    try:
        backend = get_backend(model, current_config, **kwargs)
    except ModelNotFoundError as e:
        if background_tasks:
            background_tasks.add_task(log_request, model, "N/A", 404, (time.time() - start_time) * 1000, None, str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except NoBackendsAvailableError as e:
        if background_tasks:
            background_tasks.add_task(log_request, model, "N/A", 503, (time.time() - start_time) * 1000, None, str(e))
        raise HTTPException(status_code=503, detail=str(e))

    mapping = next((m for m in current_config.model_mappings if m.model_id == model), None)
    resolved_model = model if mapping else fallback_id
    return backend, resolved_model


def _enforce_context_limit(backend, resolved_model: str, prompt_tokens: int, start_time: float, background_tasks: BackgroundTasks, error_type: str = "exceed_context_size_error", include_code: bool = True):
    limit = get_backend_limit(backend.id)
    if limit is not None and prompt_tokens > limit:
        err_msg = f"request ({prompt_tokens} tokens) exceeds the available context size ({limit} tokens), try increasing it"
        background_tasks.add_task(log_request, resolved_model, backend.url, 400, (time.time() - start_time) * 1000, UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=0, total_tokens=prompt_tokens), err_msg)
        error = {"message": err_msg, "type": error_type}
        if include_code:
            error["code"] = 400
        raise HTTPException(status_code=400, detail={"error": error})


def _usage_from_dict(u: dict, fallback_prompt: int = 0) -> UsageInfo:
    """Build UsageInfo from either OpenAI-style (prompt_tokens/completion_tokens)
    or Anthropic/Responses-style (input_tokens/output_tokens) usage objects."""
    prompt = u.get("prompt_tokens", u.get("input_tokens", fallback_prompt))
    completion = u.get("completion_tokens", u.get("output_tokens", 0))
    return UsageInfo(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=u.get("total_tokens", prompt + completion),
        prompt_tokens_details=u.get("prompt_tokens_details"),
        completion_tokens_details=u.get("completion_tokens_details"),
        cache_creation_input_tokens=u.get("cache_creation_input_tokens"),
        cache_read_input_tokens=u.get("cache_read_input_tokens"),
    )


def _openai_usage(data: dict, prompt_tokens: int) -> UsageInfo:
    if data.get("usage"):
        return _usage_from_dict(data["usage"], prompt_tokens)
    return UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=0, total_tokens=prompt_tokens)


def _ollama_usage(data: dict, prompt_tokens: int) -> UsageInfo:
    pt = data.get("prompt_eval_count", 0) or 0
    return UsageInfo(prompt_tokens=pt, completion_tokens=0, total_tokens=pt)


def _force_include_usage(payload: dict):
    """Force the backend to include token usage in the stream so we get accurate metrics."""
    if "stream_options" not in payload:
        payload["stream_options"] = {"include_usage": True}
    elif isinstance(payload["stream_options"], dict):
        payload["stream_options"]["include_usage"] = True


def _backend_error_payload(e: httpx.HTTPStatusError, include_code: bool) -> tuple[dict, str]:
    try:
        backend_error = e.response.json()
    except Exception:
        backend_error = None
    if not isinstance(backend_error, dict) or "error" not in backend_error:
        error = {"message": e.response.text, "type": "api_error"}
        if include_code:
            error["code"] = e.response.status_code
        backend_error = {"error": error}
    err_obj = backend_error.get("error")
    error_details = err_obj.get("message", e.response.text) if isinstance(err_obj, dict) else e.response.text
    return backend_error, error_details


def _sse_error_chunk(error_payload: dict, anthropic: bool) -> bytes:
    msg = json.dumps(error_payload)
    if anthropic:
        return f"event: error\ndata: {msg}\n\n".encode("utf-8")
    return f"data: {msg}\n\ndata: [DONE]\n\n".encode("utf-8")


class _StreamState:
    """Mutable accumulator a per-protocol chunk parser fills in while a stream is relayed."""

    def __init__(self):
        self.accumulated_content = ""
        self.usage_obj: Optional[UsageInfo] = None
        self.got_first_token = False


def _parse_chat_chunk(data_json: dict, state: _StreamState, prompt_tokens: int):
    if data_json.get("choices"):
        state.got_first_token = True
        delta = data_json["choices"][0].get("delta", {})
        if delta.get("content"):
            state.accumulated_content += delta["content"]
    if data_json.get("usage"):
        state.usage_obj = _usage_from_dict(data_json["usage"], prompt_tokens)


def _parse_responses_chunk(data_json: dict, state: _StreamState, prompt_tokens: int):
    # llama.cpp-style chunks carry an `output` array; spec-compliant Responses
    # streams send typed events such as response.output_text.delta.
    if data_json.get("output"):
        state.got_first_token = True
        for item in data_json["output"]:
            if item.get("type") == "text" and "text" in item:
                state.accumulated_content += item["text"]
            elif item.get("type") == "message" and isinstance(item.get("message"), dict):
                content = item["message"].get("content")
                if content:
                    state.accumulated_content += content
    if data_json.get("type") == "response.output_text.delta" and data_json.get("delta"):
        state.got_first_token = True
        state.accumulated_content += data_json["delta"]
    if data_json.get("usage"):
        state.usage_obj = _usage_from_dict(data_json["usage"], prompt_tokens)
    elif isinstance(data_json.get("response"), dict) and data_json["response"].get("usage"):
        state.usage_obj = _usage_from_dict(data_json["response"]["usage"], prompt_tokens)


def _parse_anthropic_chunk(data_json: dict, state: _StreamState, prompt_tokens: int):
    if data_json.get("type") == "content_block_delta" and "text" in data_json.get("delta", {}):
        state.got_first_token = True
        state.accumulated_content += data_json["delta"]["text"]

    usage = data_json.get("usage")
    if not usage and isinstance(data_json.get("message"), dict):
        usage = data_json["message"].get("usage")
    if not usage:
        return

    if state.usage_obj is None:
        state.usage_obj = UsageInfo(
            prompt_tokens=usage.get("input_tokens", prompt_tokens),
            completion_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("input_tokens", prompt_tokens) + usage.get("output_tokens", 0),
            cache_creation_input_tokens=usage.get("cache_creation_input_tokens"),
            cache_read_input_tokens=usage.get("cache_read_input_tokens"),
        )
    else:
        # message_delta usage reports cumulative totals — assign, don't accumulate
        if "input_tokens" in usage:
            state.usage_obj.prompt_tokens = usage["input_tokens"]
        if "output_tokens" in usage:
            state.usage_obj.completion_tokens = usage["output_tokens"]
        if usage.get("cache_creation_input_tokens") is not None:
            state.usage_obj.cache_creation_input_tokens = usage["cache_creation_input_tokens"]
        if usage.get("cache_read_input_tokens") is not None:
            state.usage_obj.cache_read_input_tokens = usage["cache_read_input_tokens"]
        state.usage_obj.total_tokens = state.usage_obj.prompt_tokens + state.usage_obj.completion_tokens


async def _stream_proxy(url: str, payload: dict, start_time: float, request_model: str, prompt_tokens: int, headers: Optional[dict], parse_chunk: Callable, anthropic: bool = False):
    state = _StreamState()
    status_code = 200
    error_details = None
    ttft_ms = None
    completion_tokens = 0

    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("POST", url, json=payload, timeout=None, headers=headers or {}) as response:
                if response.is_error:
                    await response.aread()
                response.raise_for_status()
                status_code = response.status_code
                async for chunk in response.aiter_lines():
                    if not chunk:
                        continue
                    if chunk.startswith("data: "):
                        data_str = chunk[6:].strip()
                        if data_str and data_str != "[DONE]":
                            try:
                                parse_chunk(json.loads(data_str), state, prompt_tokens)
                                if state.got_first_token and ttft_ms is None:
                                    ttft_ms = (time.time() - start_time) * 1000
                            except Exception:
                                pass
                    yield (chunk + "\n\n").encode("utf-8")

            # Fallback token count for the accumulated content (used when the
            # backend never reported usage)
            completion_tokens = count_tokens(state.accumulated_content, request_model)
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            backend_error, error_details = _backend_error_payload(e, include_code=not anthropic)
            yield _sse_error_chunk(backend_error, anthropic)
        except httpx.RequestError as e:
            status_code = 502
            error_details = f"Connection error ({type(e).__name__}): {str(e)}"
            error = {"message": error_details, "type": "api_error"}
            if not anthropic:
                error["code"] = 502
            yield _sse_error_chunk({"error": error}, anthropic)
        except Exception as e:
            status_code = 500
            error_details = f"Internal proxy stream error ({type(e).__name__}): {str(e)}"
            error = {"message": error_details, "type": "api_error"}
            if not anthropic:
                error["code"] = 500
            yield _sse_error_chunk({"error": error}, anthropic)
        finally:
            duration = (time.time() - start_time) * 1000
            if state.usage_obj:
                usage = state.usage_obj
                completion_tokens = usage.completion_tokens
            else:
                usage = UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=prompt_tokens + completion_tokens)

            tokens_per_second = None
            if ttft_ms is not None and duration > ttft_ms:
                generation_time_s = (duration - ttft_ms) / 1000.0
                if generation_time_s > 0 and completion_tokens > 0:
                    tokens_per_second = completion_tokens / generation_time_s

            # SQLite writes block; keep them off the event loop
            await asyncio.to_thread(log_request, request_model, url, status_code, duration, usage, error_details, ttft_ms, tokens_per_second)


async def _proxy_post(target_url: str, payload: dict, headers: dict, request_model: str, prompt_tokens: int, start_time: float, background_tasks: BackgroundTasks, extract_usage: Callable):
    status_code = 200
    usage = None
    error_details = None
    ttft_ms = None
    tokens_per_second = None

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                target_url,
                json=payload,
                timeout=None,
                headers=headers,
            )
            response.raise_for_status()
            status_code = response.status_code
            data = response.json()
            usage = extract_usage(data, prompt_tokens)

            # llama.cpp includes timings even on OpenAI/Anthropic-shaped responses
            if "timings" in data:
                ttft_ms = data.get("timings", {}).get("prompt_ms")
                tokens_per_second = data.get("timings", {}).get("predicted_per_second")

            return JSONResponse(status_code=status_code, content=data)
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_details = f"Backend HTTP {status_code}: {e.response.text}"
            raise HTTPException(status_code=status_code, detail=f"Backend error: {error_details}")
        except httpx.RequestError as e:
            status_code = 502
            error_details = f"Connection error ({type(e).__name__}): {str(e)}"
            raise HTTPException(status_code=502, detail=f"Error connecting to backend: {error_details}")
        except Exception as e:
            status_code = 500
            error_details = f"Internal error ({type(e).__name__}): {str(e)}"
            raise HTTPException(status_code=500, detail=f"Internal proxy error: {error_details}")
        finally:
            duration = (time.time() - start_time) * 1000
            if not usage:
                usage = UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=0, total_tokens=prompt_tokens)
            background_tasks.add_task(log_request, request_model, target_url, status_code, duration, usage, error_details, ttft_ms, tokens_per_second)


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, background_tasks: BackgroundTasks):
    start_time = time.time()
    backend, resolved_model = _resolve_backend(request.model, start_time, background_tasks)

    payload = request.model_dump(exclude_none=True)
    # Estimate prompt tokens by counting the JSON representation of messages and tools
    # This provides a much more accurate estimate for complex tool-calling workloads
    content_to_count = json.dumps(payload.get("messages", []))
    if "tools" in payload:
        content_to_count += json.dumps(payload["tools"])

    prompt_tokens = count_tokens(content_to_count, resolved_model)
    _enforce_context_limit(backend, resolved_model, prompt_tokens, start_time, background_tasks)

    target_url = f"{backend.url.rstrip('/')}/v1/chat/completions"
    auth_headers = backend_auth_headers(backend)

    if request.stream:
        _force_include_usage(payload)
        return StreamingResponse(_stream_proxy(target_url, payload, start_time, resolved_model, prompt_tokens, auth_headers, _parse_chat_chunk), media_type="text/event-stream")

    return await _proxy_post(target_url, payload, auth_headers, resolved_model, prompt_tokens, start_time, background_tasks, _openai_usage)


@app.post("/v1/responses")
async def responses_api(request: ResponsesRequest, background_tasks: BackgroundTasks):
    start_time = time.time()
    backend, resolved_model = _resolve_backend(request.model, start_time, background_tasks)

    payload = request.model_dump(exclude_none=True)
    content_to_count = ""
    if "instructions" in payload:
        content_to_count += str(payload["instructions"])
    if "input" in payload:
        content_to_count += json.dumps(payload["input"])
    if "tools" in payload:
        content_to_count += json.dumps(payload["tools"])

    prompt_tokens = count_tokens(content_to_count, resolved_model)
    _enforce_context_limit(backend, resolved_model, prompt_tokens, start_time, background_tasks)

    target_url = f"{backend.url.rstrip('/')}/v1/responses"
    auth_headers = backend_auth_headers(backend)

    if request.stream:
        _force_include_usage(payload)
        return StreamingResponse(_stream_proxy(target_url, payload, start_time, resolved_model, prompt_tokens, auth_headers, _parse_responses_chunk), media_type="text/event-stream")

    return await _proxy_post(target_url, payload, auth_headers, resolved_model, prompt_tokens, start_time, background_tasks, _openai_usage)


@app.post("/v1/messages/count_tokens")
async def anthropic_count_tokens_api(request: AnthropicMessageRequest):
    # Intentionally not logged: token counting isn't inference and would skew
    # request/usage metrics.
    backend, _ = _resolve_backend(request.model, time.time())

    target_url = f"{backend.url.rstrip('/')}/v1/messages/count_tokens"
    payload = request.model_dump(exclude_none=True)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                target_url,
                json=payload,
                timeout=None,
                headers=backend_auth_headers(backend, anthropic=True),
            )
            response.raise_for_status()
            return JSONResponse(status_code=response.status_code, content=response.json())
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            raise HTTPException(status_code=status_code, detail=f"Backend error: Backend HTTP {status_code}: {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Error connecting to backend: Connection error ({type(e).__name__}): {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Internal proxy error: Internal error ({type(e).__name__}): {str(e)}")


@app.post("/v1/messages")
async def anthropic_messages_api(request: AnthropicMessageRequest, background_tasks: BackgroundTasks):
    start_time = time.time()
    backend, resolved_model = _resolve_backend(request.model, start_time, background_tasks)

    payload = request.model_dump(exclude_none=True)
    content_to_count = json.dumps(payload.get("messages", []))
    if "system" in payload:
        content_to_count += str(payload["system"])
    if "tools" in payload:
        content_to_count += json.dumps(payload["tools"])

    prompt_tokens = count_tokens(content_to_count, resolved_model)
    _enforce_context_limit(backend, resolved_model, prompt_tokens, start_time, background_tasks, error_type="invalid_request_error", include_code=False)

    target_url = f"{backend.url.rstrip('/')}/v1/messages"
    auth_headers = backend_auth_headers(backend, anthropic=True)

    if request.stream:
        return StreamingResponse(_stream_proxy(target_url, payload, start_time, resolved_model, prompt_tokens, auth_headers, _parse_anthropic_chunk, anthropic=True), media_type="text/event-stream")

    return await _proxy_post(target_url, payload, auth_headers, resolved_model, prompt_tokens, start_time, background_tasks, _openai_usage)


@app.post("/v1/embeddings")
async def embeddings(request: EmbeddingRequest, background_tasks: BackgroundTasks):
    start_time = time.time()
    backend, resolved_model = _resolve_backend(request.model, start_time, background_tasks, default_model_override=current_config.default_embedding_model_id)

    payload = request.model_dump(exclude_none=True)

    if isinstance(request.input, str):
        content_to_count = request.input
    elif isinstance(request.input, list) and request.input and isinstance(request.input[0], str):
        content_to_count = "\n".join(request.input)
    else:
        content_to_count = json.dumps(payload.get("input"))

    prompt_tokens = count_tokens(content_to_count, resolved_model)
    _enforce_context_limit(backend, resolved_model, prompt_tokens, start_time, background_tasks)

    target_url = f"{backend.url.rstrip('/')}/v1/embeddings"
    return await _proxy_post(target_url, payload, backend_auth_headers(backend), resolved_model, prompt_tokens, start_time, background_tasks, _openai_usage)


async def _ollama_embed_passthrough(request: Request, background_tasks: BackgroundTasks, path: str):
    start_time = time.time()
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    model = body.get("model")
    if not model:
        raise HTTPException(status_code=400, detail="'model' field is required")

    backend, resolved_model = _resolve_backend(model, start_time, background_tasks, default_model_override=current_config.default_embedding_model_id)

    target_url = f"{backend.url.rstrip('/')}{path}"
    return await _proxy_post(target_url, body, backend_auth_headers(backend), resolved_model, 0, start_time, background_tasks, _ollama_usage)


@app.post("/api/embed")
async def ollama_embed(request: Request, background_tasks: BackgroundTasks):
    return await _ollama_embed_passthrough(request, background_tasks, "/api/embed")


@app.post("/api/embeddings")
async def ollama_embeddings(request: Request, background_tasks: BackgroundTasks):
    return await _ollama_embed_passthrough(request, background_tasks, "/api/embeddings")


def _max_backend_limit(backend_ids) -> Optional[int]:
    max_limit = None
    for backend_id in backend_ids:
        limit = get_backend_limit(backend_id)
        if limit is not None and (max_limit is None or limit > max_limit):
            max_limit = limit
    return max_limit


@app.get("/v1/models")
async def list_models():
    models = []
    seen_models = set()
    for mapping in current_config.model_mappings:
        if mapping.model_id not in seen_models:
            seen_models.add(mapping.model_id)
            limit = _max_backend_limit(mapping.backend_ids)
            models.append({
                "id": mapping.model_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "multiproxy",
                "context_length": limit or 4096
            })

    return {"object": "list", "data": models}


@app.get("/v1/models/browser")
async def models_browser():
    backends_by_id = {b.id: b for b in current_config.backends}
    default_chat = current_config.default_model_id
    default_embed = current_config.default_embedding_model_id

    data = []
    seen = set()
    for mapping in current_config.model_mappings:
        if mapping.model_id in seen:
            continue
        seen.add(mapping.model_id)

        backend_entries = []
        for backend_id in mapping.backend_ids:
            backend = backends_by_id.get(backend_id)
            backend_entries.append({
                "id": backend_id,
                "url": backend.url if backend else None,
                "configured": backend is not None,
                "context_length": get_backend_limit(backend_id),
            })

        data.append({
            "id": mapping.model_id,
            "object": "model",
            "owned_by": "multiproxy",
            "context_length": _max_backend_limit(mapping.backend_ids),
            "is_default": mapping.model_id == default_chat,
            "is_default_embedding": mapping.model_id == default_embed,
            "backends": backend_entries,
        })

    return {
        "object": "list",
        "default_model_id": default_chat,
        "default_embedding_model_id": default_embed,
        "data": data,
    }
