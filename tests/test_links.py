import re
from datetime import datetime

_BASE62_RE = re.compile(r"^[0-9a-zA-Z]{6,8}$")
_ALIAS_RE = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")


def test_create_link_returns_full_shape(client_a):
    resp = client_a.post("/api/v1/links", json={"url": "https://example.com"})
    assert resp.status_code == 201
    body = resp.json()

    assert _BASE62_RE.fullmatch(body["code"])
    assert body["short_url"].endswith("/" + body["code"])
    assert body["long_url"] == "https://example.com/"
    assert "created_at" in body
    assert "expires_at" in body
    assert body["is_active"] is True
    assert "max_clicks" in body


def test_invalid_url_scheme_rejected(client_a):
    resp = client_a.post("/api/v1/links", json={"url": "ftp://example.com"})
    # Pydantic HttpUrl rejects this -> 422
    assert resp.status_code == 422


def test_custom_alias_success(client_a):
    alias = "brendan_123"
    assert _ALIAS_RE.fullmatch(alias)

    resp = client_a.post(
        "/api/v1/links",
        json={"url": "https://example.com", "custom_alias": alias},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["code"] == alias
    assert body["short_url"].endswith("/" + alias)


def test_custom_alias_collision_returns_409(client_a):
    alias = "taken_alias"
    first = client_a.post("/api/v1/links", json={"url": "https://example.com", "custom_alias": alias})
    assert first.status_code == 201

    second = client_a.post("/api/v1/links", json={"url": "https://example.com", "custom_alias": alias})
    assert second.status_code == 409


def test_custom_alias_invalid_rejected(client_a):
    resp = client_a.post(
        "/api/v1/links",
        json={"url": "https://example.com", "custom_alias": "!!bad!!"},
    )
    assert resp.status_code == 422


def test_expires_in_seconds_persists(client_a):
    resp = client_a.post(
        "/api/v1/links",
        json={"url": "https://example.com", "expires_in_seconds": 60},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["expires_at"] is not None

    # confirm it's parseable ISO datetime
    datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00"))


def test_max_clicks_persists(client_a):
    resp = client_a.post(
        "/api/v1/links",
        json={"url": "https://example.com", "max_clicks": 5},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["max_clicks"] == 5


def test_get_link_stats_includes_max_clicks(client_a):
    create = client_a.post("/api/v1/links", json={"url": "https://example.com", "max_clicks": 5})
    assert create.status_code == 201
    code = create.json()["code"]

    stats = client_a.get(f"/api/v1/links/{code}")
    assert stats.status_code == 200
    data = stats.json()
    assert data["code"] == code
    assert data["max_clicks"] == 5
