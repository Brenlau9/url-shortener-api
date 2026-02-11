import os
import time

from fastapi.testclient import TestClient

from urlshortenerapi.main import app


def assert_error_shape(resp, expected_code: str):
    # All standardized errors should be JSON
    assert resp.headers.get("content-type", "").startswith("application/json")

    body = resp.json()
    assert "error" in body
    assert isinstance(body["error"], dict)

    assert body["error"].get("code") == expected_code
    msg = body["error"].get("message")
    assert isinstance(msg, str)
    assert msg.strip() != ""


def test_401_unauthorized_error_shape():
    """
    Missing X-API-Key should produce 401 in the standard error format.
    Use a fresh client so we don't mutate fixture headers.
    """
    c = TestClient(app)
    resp = c.post("/api/v1/links", json={"url": "https://example.com"})
    assert resp.status_code == 401
    assert_error_shape(resp, "UNAUTHORIZED")


def test_403_forbidden_disabled_link(client_a):
    """
    Disabled link should return 403 on redirect.
    """
    create = client_a.post("/api/v1/links", json={"url": "https://example.com"})
    assert create.status_code == 201
    code = create.json()["code"]

    disable = client_a.patch(f"/api/v1/links/{code}", json={"is_active": False})
    assert disable.status_code == 200

    resp = client_a.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 403
    assert_error_shape(resp, "FORBIDDEN")


def test_404_not_found_error_shape(client_a):
    """
    Unknown short code should return 404 on redirect.
    """
    resp = client_a.get("/this_code_should_not_exist_12345", follow_redirects=False)
    assert resp.status_code == 404
    assert_error_shape(resp, "NOT_FOUND")


def test_409_conflict_alias_taken(client_a):
    """
    Alias collision should return 409 in the standard error format.
    """
    alias = "taken_alias_123"

    first = client_a.post(
        "/api/v1/links", json={"url": "https://example.com", "custom_alias": alias}
    )
    assert first.status_code == 201

    second = client_a.post(
        "/api/v1/links", json={"url": "https://example.com/2", "custom_alias": alias}
    )
    assert second.status_code == 409
    assert_error_shape(second, "CONFLICT")


def test_410_gone_expired_link(client_a):
    """
    Expired link should return 410 on redirect.
    """
    create = client_a.post(
        "/api/v1/links", json={"url": "https://example.com", "expires_in_seconds": 1}
    )
    assert create.status_code == 201
    code = create.json()["code"]

    time.sleep(1.2)

    resp = client_a.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 410
    assert_error_shape(resp, "GONE")


def test_429_rate_limited_create_includes_headers(client_a):
    """
    Exceed create rate limit should return 429 with Retry-After
    and the standard error format.
    Your isolate_db fixture clears Redis keys, so this stays deterministic.
    """
    os.environ["CREATE_LIMIT"] = "2"
    os.environ["CREATE_WINDOW"] = "60"

    r1 = client_a.post("/api/v1/links", json={"url": "https://example.com/1"})
    assert r1.status_code == 201

    r2 = client_a.post("/api/v1/links", json={"url": "https://example.com/2"})
    assert r2.status_code == 201

    r3 = client_a.post("/api/v1/links", json={"url": "https://example.com/3"})
    assert r3.status_code == 429
    assert "Retry-After" in r3.headers
    assert_error_shape(r3, "RATE_LIMITED")
