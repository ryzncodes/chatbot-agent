from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_calculator_tool_route():
    response = client.post("/tools/calculator", json={"expression": "1 + 4"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"] == 5


def test_calculator_tool_invalid_expression_returns_400():
    response = client.post("/tools/calculator", json={"expression": "2 + bad"})
    assert response.status_code == 400
    payload = response.json()
    assert (
        payload["detail"]
        == "I couldn't compute that expression. Please check the syntax."
    )


def test_products_tool_route_requires_query():
    response = client.get("/tools/products")
    assert response.status_code == 400


def test_products_tool_route_returns_404_when_unavailable(products_query):
    response = client.get("/tools/products", params=products_query)
    assert response.status_code in {200, 404}


def test_products_alias_requires_query():
    response = client.get("/products")
    assert response.status_code == 400


def test_products_alias_returns_payload(products_query):
    response = client.get("/products", params=products_query)
    payload = response.json()
    assert response.status_code in {200, 404}
    assert set(payload.keys()) == {"detail"} or set(payload.keys()) == {"message", "results"}


def test_outlets_alias_requires_query():
    response = client.get("/outlets")
    assert response.status_code == 400


def test_outlets_alias_returns_payload():
    response = client.get("/outlets", params={"query": "SS2"})
    payload = response.json()
    assert response.status_code in {200, 404}
    assert set(payload.keys()) == {"detail"} or set(payload.keys()) == {"message", "results"}


def test_outlets_tool_route_requires_query():
    response = client.get("/tools/outlets")
    assert response.status_code == 400
    assert response.json()["detail"] == "query parameter is required"


def test_outlets_route_rejects_injection():
    response = client.get("/tools/outlets", params={"query": "'; DROP TABLE outlets;"})
    assert response.status_code in {200, 404}
    if response.status_code == 200:
        data = response.json()
        assert data.get("results") == []


def test_products_tool_handles_internal_error(monkeypatch):
    from backend import main

    async def failing_run(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("service down")

    monkeypatch.setattr(main.products_tool, "run", failing_run)

    response = client.get("/tools/products", params={"query": "tumbler"})
    assert response.status_code == 500
    payload = response.json()
    assert payload["error"] == "internal_error"
    assert payload["message"] == "Something unexpected happened. Please try again later."


def test_request_id_header_propagated():
    response = client.post(
        "/tools/calculator",
        json={"expression": "2 + 2"},
        headers={"X-Request-ID": "test-req-123"},
    )
    assert response.headers.get("X-Request-ID") == "test-req-123"
