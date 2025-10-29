from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_openapi_contains_expected_paths():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    expected = [
        "/chat",
        "/tools/calculator",
        "/tools/products",
        "/tools/outlets",
        "/products",
        "/health",
    ]

    for path in expected:
        assert path in paths, f"Missing {path} from OpenAPI paths"

    assert "post" in paths["/chat"]
    assert "get" in paths["/products"]
