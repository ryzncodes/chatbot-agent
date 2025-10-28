from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_chat_unknown_intent_triggers_fallback():
    response = client.post(
        "/chat",
        json={
            "conversation_id": "conv-unknown",
            "role": "user",
            "content": "blorbledygook",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "fallback"
    assert "rephrase" in payload["message"].lower()
