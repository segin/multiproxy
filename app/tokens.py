import tiktoken

def count_tokens(text: str, model_id: str) -> int:
    if not text:
        return 0
        
    try:
        encoding = tiktoken.encoding_for_model(model_id)
    except KeyError:
        # Fallback to standard OpenAI encoding for unknown or custom models
        encoding = tiktoken.get_encoding("cl100k_base")
        
    return len(encoding.encode(text))
