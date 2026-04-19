from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from app.schemas import ChatCompletionRequest, UsageInfo, ResponsesRequest, AnthropicMessageRequest
from app.config import Config
from app.mapping import get_backend, ModelNotFoundError, NoBackendsAvailableError
from app.tokens import count_tokens
import httpx
import time
import json
from app.logger import log_request, init_db, setup_logging
from app.config import load_config
from app.discovery import discover_backend_limits, get_backend_limit
from contextlib import asynccontextmanager

# This will be initialized properly later; for tests we can patch it
current_config = Config(backends=[], model_mappings=[])

@asynccontextmanager
async def lifespan(app: FastAPI):
    global current_config
    setup_logging()
    init_db()
    try:
        current_config = load_config("config.yaml")
    except FileNotFoundError:
        print("Warning: config.yaml not found. Using empty configuration.")
    await discover_backend_limits(current_config)
    yield

app = FastAPI(title="MultiProxy", lifespan=lifespan)

async def stream_backend_response(url: str, payload: dict, start_time: float, request_model: str, prompt_tokens: int):
    completion_tokens = 0
    status_code = 200
    error_details = None
    accumulated_content = ""
    usage_obj = None
    ttft_ms = None
    
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("POST", url, json=payload, timeout=600.0) as response:
                if response.is_error:
                    await response.aread()
                response.raise_for_status()
                status_code = response.status_code
                async for chunk in response.aiter_lines():
                    if not chunk:
                        continue
                    if chunk.startswith("data: "):
                        data_str = chunk[6:]
                        if data_str.strip() != "[DONE]":
                            try:
                                data_json = json.loads(data_str)
                                if "choices" in data_json and len(data_json["choices"]) > 0:
                                    if ttft_ms is None:
                                        ttft_ms = (time.time() - start_time) * 1000
                                    delta = data_json["choices"][0].get("delta", {})
                                    if "content" in delta and delta["content"]:
                                        accumulated_content += delta["content"]
                                if "usage" in data_json and data_json["usage"]:
                                    usage_obj = UsageInfo(**data_json["usage"])
                            except Exception:
                                pass
                    yield (chunk + "\n\n").encode("utf-8")
            
            # Final token count for the accumulated content
            completion_tokens = count_tokens(accumulated_content, request_model)
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            try:
                backend_error = e.response.json()
                if "error" not in backend_error:
                    backend_error = {"error": {"message": e.response.text, "type": "api_error", "code": status_code}}
            except Exception:
                backend_error = {"error": {"message": e.response.text, "type": "api_error", "code": status_code}}
            error_msg = json.dumps(backend_error)
            error_details = backend_error.get("error", {}).get("message", e.response.text)
            yield f"data: {error_msg}\n\ndata: [DONE]\n\n".encode("utf-8")
        except httpx.RequestError as e:
            status_code = 502
            error_details = f"Connection error ({type(e).__name__}): {str(e)}"
            error_msg = json.dumps({"error": {"message": error_details, "type": "api_error", "code": 502}})
            yield f"data: {error_msg}\n\ndata: [DONE]\n\n".encode("utf-8")
        except Exception as e:
            status_code = 500
            error_details = f"Internal proxy stream error ({type(e).__name__}): {str(e)}"
            error_msg = json.dumps({"error": {"message": error_details, "type": "api_error", "code": 500}})
            yield f"data: {error_msg}\n\ndata: [DONE]\n\n".encode("utf-8")
        finally:
            duration = (time.time() - start_time) * 1000
            if usage_obj:
                usage = usage_obj
                completion_tokens = usage.completion_tokens
            else:
                usage = UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=prompt_tokens + completion_tokens)
            
            tokens_per_second = None
            if ttft_ms is not None and duration > ttft_ms:
                generation_time_s = (duration - ttft_ms) / 1000.0
                if generation_time_s > 0 and completion_tokens > 0:
                    tokens_per_second = completion_tokens / generation_time_s
                    
            log_request(request_model, url, status_code, duration, usage, error_details, ttft_ms, tokens_per_second)

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, background_tasks: BackgroundTasks):
    start_time = time.time()
    try:
        backend = get_backend(request.model, current_config)
        mapping = next((m for m in current_config.model_mappings if m.model_id == request.model), None)
        resolved_model = request.model if mapping else current_config.default_model_id
    except ModelNotFoundError as e:
        background_tasks.add_task(log_request, request.model, "N/A", 404, (time.time() - start_time) * 1000, None, str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except NoBackendsAvailableError as e:
        background_tasks.add_task(log_request, request.model, "N/A", 503, (time.time() - start_time) * 1000, None, str(e))
        raise HTTPException(status_code=503, detail=str(e))
        
    payload_dict = request.model_dump(exclude_none=True)
    # Estimate prompt tokens by counting the JSON representation of messages and tools
    # This provides a much more accurate estimate for complex tool-calling workloads
    content_to_count = json.dumps(payload_dict.get("messages", []))
    if "tools" in payload_dict:
        content_to_count += json.dumps(payload_dict["tools"])
    
    prompt_tokens = count_tokens(content_to_count, resolved_model)
    limit = get_backend_limit(backend.id)
    if limit is not None and prompt_tokens > limit:
        err_msg = f"request ({prompt_tokens} tokens) exceeds the available context size ({limit} tokens), try increasing it"
        background_tasks.add_task(log_request, resolved_model, backend.url, 400, (time.time() - start_time) * 1000, UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=0, total_tokens=prompt_tokens), err_msg)
        raise HTTPException(status_code=400, detail={"error": {"code": 400, "message": err_msg, "type": "exceed_context_size_error"}})

    target_url = f"{backend.url.rstrip('/')}/v1/chat/completions"
    payload = request.model_dump(exclude_none=True)
    
    if request.stream:
        # Force the backend to include token usage in the stream so we get accurate metrics
        if "stream_options" not in payload:
            payload["stream_options"] = {"include_usage": True}
        elif isinstance(payload["stream_options"], dict):
            payload["stream_options"]["include_usage"] = True
            
        return StreamingResponse(stream_backend_response(target_url, payload, start_time, resolved_model, prompt_tokens), media_type="text/event-stream")
    
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
                timeout=600.0
            )
            response.raise_for_status()
            status_code = response.status_code
            data = response.json()
            if "usage" in data:
                usage = UsageInfo(**data["usage"])
            else:
                usage = UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=0, total_tokens=prompt_tokens)
            
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
            background_tasks.add_task(log_request, resolved_model, target_url, status_code, duration, usage, error_details, ttft_ms, tokens_per_second)

async def stream_responses_backend_response(url: str, payload: dict, start_time: float, request_model: str, prompt_tokens: int):
    completion_tokens = 0
    status_code = 200
    error_details = None
    accumulated_content = ""
    usage_obj = None
    ttft_ms = None
    
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("POST", url, json=payload, timeout=600.0) as response:
                if response.is_error:
                    await response.aread()
                response.raise_for_status()
                status_code = response.status_code
                async for chunk in response.aiter_lines():
                    if not chunk:
                        continue
                    if chunk.startswith("data: "):
                        data_str = chunk[6:]
                        if data_str.strip() != "[DONE]":
                            try:
                                data_json = json.loads(data_str)
                                if "output" in data_json and len(data_json["output"]) > 0:
                                    if ttft_ms is None:
                                        ttft_ms = (time.time() - start_time) * 1000
                                    for item in data_json["output"]:
                                        if item.get("type") == "text" and "text" in item:
                                            accumulated_content += item["text"]
                                        elif item.get("type") == "message" and "message" in item and "content" in item["message"]:
                                            if item["message"]["content"]:
                                                accumulated_content += item["message"]["content"]
                                if "usage" in data_json and data_json["usage"]:
                                    usage_obj = UsageInfo(**data_json["usage"])
                            except Exception:
                                pass
                    yield (chunk + "\n\n").encode("utf-8")
            
            # Final token count for the accumulated content
            completion_tokens = count_tokens(accumulated_content, request_model)
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            try:
                backend_error = e.response.json()
                if "error" not in backend_error:
                    backend_error = {"error": {"message": e.response.text, "type": "api_error", "code": status_code}}
            except Exception:
                backend_error = {"error": {"message": e.response.text, "type": "api_error", "code": status_code}}
            error_msg = json.dumps(backend_error)
            error_details = backend_error.get("error", {}).get("message", e.response.text)
            yield f"data: {error_msg}\n\ndata: [DONE]\n\n".encode("utf-8")
        except httpx.RequestError as e:
            status_code = 502
            error_details = f"Connection error ({type(e).__name__}): {str(e)}"
            error_msg = json.dumps({"error": {"message": error_details, "type": "api_error", "code": 502}})
            yield f"data: {error_msg}\n\ndata: [DONE]\n\n".encode("utf-8")
        except Exception as e:
            status_code = 500
            error_details = f"Internal proxy stream error ({type(e).__name__}): {str(e)}"
            error_msg = json.dumps({"error": {"message": error_details, "type": "api_error", "code": 500}})
            yield f"data: {error_msg}\n\ndata: [DONE]\n\n".encode("utf-8")
        finally:
            duration = (time.time() - start_time) * 1000
            if usage_obj:
                usage = usage_obj
                completion_tokens = usage.completion_tokens
            else:
                usage = UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=prompt_tokens + completion_tokens)
            
            tokens_per_second = None
            if ttft_ms is not None and duration > ttft_ms:
                generation_time_s = (duration - ttft_ms) / 1000.0
                if generation_time_s > 0 and completion_tokens > 0:
                    tokens_per_second = completion_tokens / generation_time_s
                    
            log_request(request_model, url, status_code, duration, usage, error_details, ttft_ms, tokens_per_second)

@app.post("/v1/responses")
async def responses_api(request: ResponsesRequest, background_tasks: BackgroundTasks):
    start_time = time.time()
    try:
        backend = get_backend(request.model, current_config)
        mapping = next((m for m in current_config.model_mappings if m.model_id == request.model), None)
        resolved_model = request.model if mapping else current_config.default_model_id
    except ModelNotFoundError as e:
        background_tasks.add_task(log_request, request.model, "N/A", 404, (time.time() - start_time) * 1000, None, str(e), None, None)
        raise HTTPException(status_code=404, detail=str(e))
    except NoBackendsAvailableError as e:
        background_tasks.add_task(log_request, request.model, "N/A", 503, (time.time() - start_time) * 1000, None, str(e), None, None)
        raise HTTPException(status_code=503, detail=str(e))
        
    payload_dict = request.model_dump(exclude_none=True)
    content_to_count = ""
    if "instructions" in payload_dict:
        content_to_count += str(payload_dict["instructions"])
    if "input" in payload_dict:
        content_to_count += json.dumps(payload_dict["input"])
    if "tools" in payload_dict:
        content_to_count += json.dumps(payload_dict["tools"])
    
    prompt_tokens = count_tokens(content_to_count, resolved_model)
    limit = get_backend_limit(backend.id)
    if limit is not None and prompt_tokens > limit:
        err_msg = f"request ({prompt_tokens} tokens) exceeds the available context size ({limit} tokens), try increasing it"
        background_tasks.add_task(log_request, resolved_model, backend.url, 400, (time.time() - start_time) * 1000, UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=0, total_tokens=prompt_tokens), err_msg, None, None)
        raise HTTPException(status_code=400, detail={"error": {"code": 400, "message": err_msg, "type": "exceed_context_size_error"}})

    target_url = f"{backend.url.rstrip("/")}/v1/responses"
    payload = request.model_dump(exclude_none=True)
    
    if request.stream:
        if "stream_options" not in payload:
            payload["stream_options"] = {"include_usage": True}
        elif isinstance(payload["stream_options"], dict):
            payload["stream_options"]["include_usage"] = True
            
        return StreamingResponse(stream_responses_backend_response(target_url, payload, start_time, resolved_model, prompt_tokens), media_type="text/event-stream")
    
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
                timeout=600.0
            )
            response.raise_for_status()
            status_code = response.status_code
            data = response.json()
            if "usage" in data:
                usage = UsageInfo(**data["usage"])
            else:
                usage = UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=0, total_tokens=prompt_tokens)
            
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
            background_tasks.add_task(log_request, resolved_model, target_url, status_code, duration, usage, error_details, ttft_ms, tokens_per_second)


async def stream_anthropic_backend_response(url: str, payload: dict, start_time: float, request_model: str, prompt_tokens: int):
    completion_tokens = 0
    status_code = 200
    error_details = None
    accumulated_content = ""
    usage_obj = None
    ttft_ms = None
    
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("POST", url, json=payload, timeout=600.0, headers={"anthropic-version": "2023-06-01", "x-api-key": "sk-dummy"}) as response:
                if response.is_error:
                    await response.aread()
                response.raise_for_status()
                status_code = response.status_code
                async for chunk in response.aiter_lines():
                    if not chunk:
                        continue
                    if chunk.startswith("data: "):
                        data_str = chunk[6:]
                        if data_str.strip() and data_str.strip() != "[DONE]":
                            try:
                                import json
                                data_json = json.loads(data_str)
                                if data_json.get("type") == "content_block_delta" and "delta" in data_json:
                                    if "text" in data_json["delta"]:
                                        if ttft_ms is None:
                                            ttft_ms = (time.time() - start_time) * 1000
                                        accumulated_content += data_json["delta"]["text"]
                                if "usage" in data_json and data_json["usage"]:
                                    u = data_json["usage"]
                                    if not usage_obj:
                                        usage_obj = UsageInfo(
                                            prompt_tokens=u.get("input_tokens", prompt_tokens),
                                            completion_tokens=u.get("output_tokens", 0),
                                            total_tokens=u.get("input_tokens", prompt_tokens) + u.get("output_tokens", 0),
                                            cache_creation_input_tokens=u.get("cache_creation_input_tokens"),
                                            cache_read_input_tokens=u.get("cache_read_input_tokens")
                                        )
                                    else:
                                        usage_obj.completion_tokens += u.get("output_tokens", 0)
                                        usage_obj.total_tokens = usage_obj.prompt_tokens + usage_obj.completion_tokens
                                elif "message" in data_json and "usage" in data_json["message"]:
                                    u = data_json["message"]["usage"]
                                    if not usage_obj:
                                        usage_obj = UsageInfo(
                                            prompt_tokens=u.get("input_tokens", prompt_tokens),
                                            completion_tokens=u.get("output_tokens", 0),
                                            total_tokens=u.get("input_tokens", prompt_tokens) + u.get("output_tokens", 0),
                                            cache_creation_input_tokens=u.get("cache_creation_input_tokens"),
                                            cache_read_input_tokens=u.get("cache_read_input_tokens")
                                        )
                                    else:
                                        usage_obj.completion_tokens += u.get("output_tokens", 0)
                                        usage_obj.total_tokens = usage_obj.prompt_tokens + usage_obj.completion_tokens
                            except Exception:
                                pass
                    yield (chunk + "\n\n").encode("utf-8")
            
            # Final token count for the accumulated content if usage missing
            if not usage_obj or usage_obj.completion_tokens == 0:
                completion_tokens = count_tokens(accumulated_content, request_model)
            else:
                completion_tokens = usage_obj.completion_tokens
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            try:
                backend_error = e.response.json()
                if "error" not in backend_error:
                    backend_error = {"error": {"message": e.response.text, "type": "api_error"}}
            except Exception:
                backend_error = {"error": {"message": e.response.text, "type": "api_error"}}
            import json
            error_msg = json.dumps(backend_error)
            error_details = backend_error.get("error", {}).get("message", e.response.text)
            yield f"data: {error_msg}\n\nevent: error\n\n".encode("utf-8")
        except httpx.RequestError as e:
            status_code = 502
            error_details = f"Connection error ({type(e).__name__}): {str(e)}"
            import json
            error_msg = json.dumps({"error": {"message": error_details, "type": "api_error"}})
            yield f"data: {error_msg}\n\nevent: error\n\n".encode("utf-8")
        except Exception as e:
            status_code = 500
            error_details = f"Internal proxy stream error ({type(e).__name__}): {str(e)}"
            import json
            error_msg = json.dumps({"error": {"message": error_details, "type": "api_error"}})
            yield f"data: {error_msg}\n\nevent: error\n\n".encode("utf-8")
        finally:
            import time
            duration = (time.time() - start_time) * 1000
            if usage_obj:
                usage = usage_obj
                completion_tokens = usage.completion_tokens
            else:
                usage = UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=prompt_tokens + completion_tokens)
            
            tokens_per_second = None
            if ttft_ms is not None and duration > ttft_ms:
                generation_time_s = (duration - ttft_ms) / 1000.0
                if generation_time_s > 0 and completion_tokens > 0:
                    tokens_per_second = completion_tokens / generation_time_s
                    
            from app.logger import log_request
            log_request(request_model, url, status_code, duration, usage, error_details, ttft_ms, tokens_per_second)

@app.post("/v1/messages/count_tokens")
async def anthropic_count_tokens_api(request: AnthropicMessageRequest):
    try:
        backend = get_backend(request.model, current_config)
        mapping = next((m for m in current_config.model_mappings if m.model_id == request.model), None)
        resolved_model = request.model if mapping else current_config.default_model_id
    except ModelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NoBackendsAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
        
    target_url = f"{backend.url.rstrip('/')}/v1/messages/count_tokens"
    payload = request.model_dump(exclude_none=True)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                target_url,
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            return JSONResponse(status_code=response.status_code, content=response.json())
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

@app.post("/v1/messages")
async def anthropic_messages_api(request: AnthropicMessageRequest, background_tasks: BackgroundTasks):
    import time
    start_time = time.time()
    try:
        backend = get_backend(request.model, current_config)
        mapping = next((m for m in current_config.model_mappings if m.model_id == request.model), None)
        resolved_model = request.model if mapping else current_config.default_model_id
    except ModelNotFoundError as e:
        background_tasks.add_task(log_request, request.model, "N/A", 404, (time.time() - start_time) * 1000, None, str(e), None, None)
        raise HTTPException(status_code=404, detail=str(e))
    except NoBackendsAvailableError as e:
        background_tasks.add_task(log_request, request.model, "N/A", 503, (time.time() - start_time) * 1000, None, str(e), None, None)
        raise HTTPException(status_code=503, detail=str(e))
        
    payload_dict = request.model_dump(exclude_none=True)
    import json
    content_to_count = json.dumps(payload_dict.get("messages", []))
    if "system" in payload_dict:
        content_to_count += str(payload_dict["system"])
    if "tools" in payload_dict:
        content_to_count += json.dumps(payload_dict["tools"])
    
    prompt_tokens = count_tokens(content_to_count, resolved_model)
    limit = get_backend_limit(backend.id)
    if limit is not None and prompt_tokens > limit:
        err_msg = f"request ({prompt_tokens} tokens) exceeds the available context size ({limit} tokens), try increasing it"
        background_tasks.add_task(log_request, resolved_model, backend.url, 400, (time.time() - start_time) * 1000, UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=0, total_tokens=prompt_tokens), err_msg, None, None)
        raise HTTPException(status_code=400, detail={"error": {"message": err_msg, "type": "invalid_request_error"}})

    target_url = f"{backend.url.rstrip('/')}/v1/messages"
    payload = request.model_dump(exclude_none=True)
    
    if request.stream:
        return StreamingResponse(stream_anthropic_backend_response(target_url, payload, start_time, resolved_model, prompt_tokens), media_type="text/event-stream")
    
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
                timeout=600.0,
                headers={"anthropic-version": "2023-06-01", "x-api-key": "sk-dummy"}
            )
            response.raise_for_status()
            status_code = response.status_code
            data = response.json()
            if "usage" in data:
                u = data["usage"]
                usage = UsageInfo(
                    prompt_tokens=u.get("input_tokens", prompt_tokens),
                    completion_tokens=u.get("output_tokens", 0),
                    total_tokens=u.get("input_tokens", prompt_tokens) + u.get("output_tokens", 0),
                    cache_creation_input_tokens=u.get("cache_creation_input_tokens"),
                    cache_read_input_tokens=u.get("cache_read_input_tokens")
                )
            else:
                usage = UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=0, total_tokens=prompt_tokens)
            
            # Anthropics format does not normally have "timings" but in case llama.cpp includes it:
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
            background_tasks.add_task(log_request, resolved_model, target_url, status_code, duration, usage, error_details, ttft_ms, tokens_per_second)

@app.get("/v1/models")

async def list_models():
    models = []
    seen_models = set()
    for mapping in current_config.model_mappings:
        if mapping.model_id not in seen_models:
            seen_models.add(mapping.model_id)
            
            limit = None
            for backend_id in mapping.backend_ids:
                l = get_backend_limit(backend_id)
                if l is not None:
                    limit = l
                    break
                    
            models.append({
                "id": mapping.model_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "multiproxy",
                "context_length": limit or 4096
            })
            
    return {"object": "list", "data": models}
