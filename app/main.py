from fastapi import FastAPI
from app.schemas import ChatCompletionRequest, ChatCompletionResponse, ChatChoice, ChatMessage, UsageInfo
import uuid

app = FastAPI(title="MultiProxy")

@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    # Dummy response to satisfy schema tests before actual proxying is implemented
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
        model=request.model,
        choices=[
            ChatChoice(
                index=0,
                message=ChatMessage(role="assistant", content="This is a mock response from MultiProxy."),
                finish_reason="stop"
            )
        ],
        usage=UsageInfo(prompt_tokens=0, completion_tokens=0, total_tokens=0)
    )
