from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, ConfigDict
import time

class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    role: str
    content: Optional[Union[str, List[Dict[str, Any]]]] = None

class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[List[str], str]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None

class ChatChoice(BaseModel):
    model_config = ConfigDict(extra="allow")
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None

class UsageInfo(BaseModel):
    model_config = ConfigDict(extra="allow")
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_tokens_details: Optional[Dict[str, int]] = None
    completion_tokens_details: Optional[Dict[str, int]] = None
    # Anthropic style fields
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None

class ChatCompletionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatChoice]
    usage: Optional[UsageInfo] = None
    system_fingerprint: Optional[str] = None

class ResponsesRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str
    instructions: Optional[str] = None
    input: Optional[Union[str, List[Dict[str, Any]]]] = None
    stream: Optional[bool] = False
    tools: Optional[List[Dict[str, Any]]] = None
    previous_response_id: Optional[str] = None

class ResponseItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str
    message: Optional[ChatMessage] = None
    text: Optional[str] = None

class ResponsesResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    object: str = "response"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    output: List[ResponseItem]
    usage: Optional[UsageInfo] = None

class AnthropicMessageRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str
    messages: List[Dict[str, Any]]
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False

class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str
    input: Union[str, List[str], List[int], List[List[int]]]
    encoding_format: Optional[str] = None
    dimensions: Optional[int] = None
    user: Optional[str] = None