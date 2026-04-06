import pytest
from app.tokens import count_tokens

def test_count_tokens_exact():
    # Test tiktoken integration for standard models
    text = "Hello, world! This is a test."
    token_count = count_tokens(text, "gpt-3.5-turbo")
    # "Hello", ",", " world", "!", " This", " is", " a", " test", "." -> 9 tokens in cl100k_base
    assert token_count == 9

def test_count_tokens_fallback():
    # Test fallback counting for unknown models
    text = "Hello, world! This is a test."
    token_count = count_tokens(text, "unknown-model-xyz")
    # The fallback could just use tiktoken cl100k_base as well or a simple word split.
    # Let's assume the fallback uses cl100k_base to be consistent.
    assert token_count == 9
    
def test_count_tokens_empty():
    assert count_tokens("", "gpt-4") == 0