import tiktoken
from typing import Union, List, Dict, Any

def count_tokens(content: Union[str, List[Dict[str, Any]]], model_id: str) -> int:
    if not content:
        return 0
        
    text_content = ""
    if isinstance(content, str):
        text_content = content
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                if "text" in item:
                    text_content += item["text"]
                elif item.get("type") == "text":
                    text_content += item.get("text", "")
                    
    if not text_content:
        return 0
        
    try:
        encoding = tiktoken.encoding_for_model(model_id)
    except KeyError:
        # Fallback to standard OpenAI encoding for unknown or custom models
        encoding = tiktoken.get_encoding("cl100k_base")
        
    return len(encoding.encode(text_content, allowed_special="all"))
