from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_chat_completions_endpoint_exists():
    payload = {
        "model": "qwen3.5-35b-a3b",
        "messages": [
            {"role": "user", "content": "Hello!"}
        ]
    }
    response = client.post("/v1/chat/completions", json=payload)
    
    # We haven't implemented the real proxying yet, but the endpoint should exist
    # and return a valid structure (or maybe a 501 Not Implemented for now, 
    # but let's assume we return a dummy response for the structure test).
    assert response.status_code in [200, 501], f"Expected 200 or 501, got {response.status_code}"
    
    if response.status_code == 200:
        data = response.json()
        assert "id" in data
        assert data.get("object") == "chat.completion"
        assert "created" in data
        assert "model" in data
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
        assert "content" in data["choices"][0]["message"]
