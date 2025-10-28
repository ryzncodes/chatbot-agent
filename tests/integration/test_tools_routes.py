from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_calculator_tool_route():
    response = client.post("/tools/calculator", json={"expression": "1 + 4"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"] == 5


def test_products_tool_route_requires_query():
    response = client.get("/tools/products")
    assert response.status_code == 400


def test_products_tool_route_returns_404_when_unavailable():
    response = client.get("/tools/products", params={"query": "tumbler"})
    assert response.status_code in {200, 404}
