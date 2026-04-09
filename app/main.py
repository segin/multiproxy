from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from app.schemas import ChatCompletionRequest, UsageInfo
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
            else:
                usage = UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=prompt_tokens + completion_tokens)
            log_request(request_model, url, status_code, duration, usage, error_details)

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
        return StreamingResponse(stream_backend_response(target_url, payload, start_time, resolved_model, prompt_tokens), media_type="text/event-stream")
    
    status_code = 200
    usage = None
    error_details = None
    
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
            background_tasks.add_task(log_request, resolved_model, target_url, status_code, duration, usage, error_details)

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
