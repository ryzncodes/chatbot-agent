from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_chat_responds_with_intent_and_action(tmp_path, monkeypatch):
    response = client.post(
        "/chat",
        json={
            "conversation_id": "conv-1",
            "role": "user",
            "content": "Can you calc 1 + 2?",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "calculate"
    assert payload["action"] == "call_calculator"
    assert payload["tool_success"] is True
    assert payload["message"] == "3"
