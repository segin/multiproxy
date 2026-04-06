from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from app.schemas import ChatCompletionRequest
from app.config import Config
from app.mapping import get_backend_url, ModelNotFoundError, NoBackendsAvailableError
import httpx

app = FastAPI(title="MultiProxy")

# This will be initialized properly later; for tests we can patch it
current_config = Config(backends=[], model_mappings=[])

async def stream_backend_response(url: str, payload: dict):
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("POST", url, json=payload, timeout=60.0) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Backend error: {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Error connecting to backend: {str(e)}")

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    try:
        backend_url = get_backend_url(request.model, current_config)
    except ModelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NoBackendsAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
        
    target_url = f"{backend_url.rstrip('/')}/v1/chat/completions"
    payload = request.model_dump(exclude_none=True)
    
    if request.stream:
        return StreamingResponse(stream_backend_response(target_url, payload), media_type="text/event-stream")
    
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
            raise HTTPException(status_code=e.response.status_code, detail=f"Backend error: {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Error connecting to backend: {str(e)}")
