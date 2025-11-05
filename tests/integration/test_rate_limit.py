from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_health_is_exempt_from_rate_limit():
    # Hit /health many times quickly; it should never rate limit
    for _ in range(30):
        resp = client.get("/health")
        assert resp.status_code == 200


def test_rate_limit_headers_present_on_success():
    # Use /chat (rate-limited route) but only once to inspect headers
    resp = client.post(
        "/chat",
        json={"conversation_id": "rl-headers", "role": "user", "content": "calc 1 + 1"},
        headers={"X-User-ID": "rl-user"},
    )
    assert resp.status_code == 200
    # Headers should be present
    assert resp.headers.get("X-RateLimit-Limit") is not None
    assert resp.headers.get("X-RateLimit-Remaining") is not None
    assert resp.headers.get("X-RateLimit-Reset") is not None


def test_rate_limit_can_trigger_429_on_burst():
    # Send a burst of /chat requests; default burst is 10/sec
    got_429 = False
    for _ in range(20):
        r = client.post(
            "/chat",
            json={
                "conversation_id": "rl-burst",
                "role": "user",
                "content": "calc 2 + 3",
            },
            headers={"X-User-ID": "rl-user"},
        )
        if r.status_code == 429:
            got_429 = True
            # validate error shape and headers
            body = r.json()
            assert body.get("error") == "rate_limit_exceeded"
            assert "retry_after_seconds" in body
            assert r.headers.get("Retry-After") is not None
            assert r.headers.get("X-RateLimit-Limit") is not None
            assert r.headers.get("X-RateLimit-Remaining") == "0"
            assert r.headers.get("X-RateLimit-Reset") is not None
            break

    assert got_429, "Expected a 429 response in a burst of requests"
