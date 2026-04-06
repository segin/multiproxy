from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from app.schemas import ChatCompletionRequest, UsageInfo
from app.config import Config
from app.mapping import get_backend_url, ModelNotFoundError, NoBackendsAvailableError
from app.tokens import count_tokens
import httpx
import time
import json
from app.logger import log_request, init_db
from app.config import load_config
from contextlib import asynccontextmanager

# This will be initialized properly later; for tests we can patch it
current_config = Config(backends=[], model_mappings=[])

@asynccontextmanager
async def lifespan(app: FastAPI):
    global current_config
    init_db()
    try:
        current_config = load_config("config.yaml")
    except FileNotFoundError:
        print("Warning: config.yaml not found. Using empty configuration.")
    yield

app = FastAPI(title="MultiProxy", lifespan=lifespan)

async def stream_backend_response(url: str, payload: dict, start_time: float, request_model: str):
    prompt_tokens = sum(count_tokens(m["content"], request_model) for m in payload.get("messages", []))
    completion_tokens = 0
    status_code = 200
    
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("POST", url, json=payload, timeout=60.0) as response:
                response.raise_for_status()
                status_code = response.status_code
                async for chunk in response.aiter_bytes():
                    # very rough approx: count 'data: {"id"' occurrences or simply count tokens on chunks
                    if b"data:" in chunk and b"[DONE]" not in chunk:
                        completion_tokens += 1
                    yield chunk
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            raise HTTPException(status_code=status_code, detail=f"Backend error: {e.response.text}")
        except httpx.RequestError as e:
            status_code = 502
            raise HTTPException(status_code=502, detail=f"Error connecting to backend: {str(e)}")
        finally:
            duration = (time.time() - start_time) * 1000
            usage = UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=prompt_tokens + completion_tokens)
            log_request(request_model, url, status_code, duration, usage)

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, background_tasks: BackgroundTasks):
    start_time = time.time()
    try:
        backend_url = get_backend_url(request.model, current_config)
    except ModelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NoBackendsAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
        
    target_url = f"{backend_url.rstrip('/')}/v1/chat/completions"
    payload = request.model_dump(exclude_none=True)
    
    if request.stream:
        return StreamingResponse(stream_backend_response(target_url, payload, start_time, request.model), media_type="text/event-stream")
    
    status_code = 200
    usage = None
    prompt_tokens = sum(count_tokens(m.content, request.model) for m in request.messages)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                target_url,
                json=payload,
                timeout=60.0
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
            raise HTTPException(status_code=status_code, detail=f"Backend error: {e.response.text}")
        except httpx.RequestError as e:
            status_code = 502
            raise HTTPException(status_code=502, detail=f"Error connecting to backend: {str(e)}")
        finally:
            duration = (time.time() - start_time) * 1000
            if not usage:
                usage = UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=0, total_tokens=prompt_tokens)
            background_tasks.add_task(log_request, request.model, target_url, status_code, duration, usage)
