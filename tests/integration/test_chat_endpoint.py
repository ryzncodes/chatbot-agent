import types

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_chat_responds_with_intent_and_action(conversation_calc_payload):
    response = client.post("/chat", json=conversation_calc_payload)

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "calculate"
    assert payload["action"] == "call_calculator"
    assert payload["tool_success"] is True
    assert payload["message"] == "3"

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    metrics_payload = metrics_response.json()
    assert metrics_payload["total_requests"] >= 1


def test_chat_missing_content_returns_400():
    response = client.post(
        "/chat",
        json={"conversation_id": "conv-err"},
    )
    assert response.status_code == 400


def test_chat_handles_missing_product_tool(monkeypatch):
    from backend import main as backend_main

    def fake_catalogue(self):
        return []

    def fake_index(self):
        return None

    monkeypatch.setattr(
        backend_main.products_tool,
        "_load_catalogue",
        types.MethodType(fake_catalogue, backend_main.products_tool),
    )
    monkeypatch.setattr(
        backend_main.products_tool,
        "_ensure_index",
        types.MethodType(fake_index, backend_main.products_tool),
    )

    response = client.post(
        "/chat",
        json={
            "conversation_id": "conv-product",
            "role": "user",
            "content": "Do you have a stainless tumbler?",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "product_info"
    assert payload["action"] == "call_products"
    assert payload["tool_success"] is False
    assert payload["message"] == "I'm still learning that."


def test_chat_handles_tool_failure(monkeypatch):
    from backend import main

    async def failing_dispatch(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("tool unavailable")

    monkeypatch.setattr(main.tool_router, "dispatch", failing_dispatch)

    response = client.post(
        "/chat",
        json={
            "conversation_id": "conv-fail",
            "role": "user",
            "content": "calc 2 + 2",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_success"] is False
    assert "issue calling that tool" in payload["message"].lower()
    assert "error" in payload["tool_data"]
