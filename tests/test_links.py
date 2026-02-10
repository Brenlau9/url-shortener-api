import re
from datetime import datetime
import secrets


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
    alias = "alias_" + secrets.token_urlsafe(8).replace("-", "_")
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
    alias = "taken_" + secrets.token_urlsafe(8).replace("-", "_")
    assert _ALIAS_RE.fullmatch(alias)

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

from sqlalchemy import create_engine, text
from urlshortenerapi.core.config import settings


def _get_link_row(code: str) -> dict:
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT code, is_active, expires_at, max_clicks, click_count, last_accessed_at, long_url
                FROM links
                WHERE code = :code
                """
            ),
            {"code": code},
        ).mappings().first()
        assert row is not None
        return dict(row)


def _set_link_fields(code: str, **fields) -> None:
    # fields keys should match columns: is_active, expires_at, max_clicks, click_count, last_accessed_at
    engine = create_engine(settings.database_url)

    sets = ", ".join([f"{k} = :{k}" for k in fields.keys()])
    params = {"code": code, **fields}

    with engine.begin() as conn:
        conn.execute(text(f"UPDATE links SET {sets} WHERE code = :code"), params)


def test_redirect_not_found_returns_404(client_a):
    resp = client_a.get("/doesnotexist", follow_redirects=False)
    assert resp.status_code == 404


def test_redirect_disabled_returns_403(client_a):
    create = client_a.post("/api/v1/links", json={"url": "https://example.com"})
    assert create.status_code == 201
    code = create.json()["code"]

    _set_link_fields(code, is_active=False)

    resp = client_a.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 403


def test_redirect_expired_returns_410(client_a):
    create = client_a.post("/api/v1/links", json={"url": "https://example.com"})
    assert create.status_code == 201
    code = create.json()["code"]

    # Force it expired by setting expires_at to a past timestamp in DB
    _set_link_fields(code, expires_at="2000-01-01T00:00:00+00:00")

    resp = client_a.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 410


def test_redirect_max_clicks_exceeded_returns_410(client_a):
    create = client_a.post("/api/v1/links", json={"url": "https://example.com", "max_clicks": 1})
    assert create.status_code == 201
    code = create.json()["code"]

    # 1st click allowed
    r1 = client_a.get(f"/{code}", follow_redirects=False)
    assert r1.status_code == 307

    # 2nd click should exceed
    r2 = client_a.get(f"/{code}", follow_redirects=False)
    assert r2.status_code == 410


def test_redirect_increments_click_count_and_updates_last_accessed_at(client_a):
    create = client_a.post("/api/v1/links", json={"url": "https://example.com"})
    assert create.status_code == 201
    code = create.json()["code"]

    before = _get_link_row(code)
    assert before["click_count"] in (0, 0)  # bigint default 0
    assert before["last_accessed_at"] is None

    resp = client_a.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 307

    after = _get_link_row(code)
    assert after["click_count"] == before["click_count"] + 1
    assert after["last_accessed_at"] is not None

def test_create_rate_limit_returns_429_and_headers(client_a, api_key_a):
    import os
    import hashlib
    from sqlalchemy import create_engine, text
    from urlshortenerapi.core.config import settings
    from urlshortenerapi.core.redis import get_redis_client

    # Tight limit for test
    os.environ["CREATE_LIMIT"] = "3"
    os.environ["CREATE_WINDOW"] = "60"

    # Look up api_key_id so we can clear Redis key for isolation
    key_hash = hashlib.sha256(api_key_a.encode("utf-8")).hexdigest()
    engine = create_engine(settings.database_url)

    with engine.connect() as conn:
        api_key_id = conn.execute(
            text("SELECT id FROM api_keys WHERE key_hash = :kh"),
            {"kh": key_hash},
        ).scalar_one()

    r = get_redis_client()
    r.delete(f"rate:create:{api_key_id}")

    # 3 allowed requests
    for _ in range(3):
        resp = client_a.post("/api/v1/links", json={"url": "https://example.com"})
        assert resp.status_code == 201
        assert resp.headers.get("X-RateLimit-Limit") == "3"
        assert "X-RateLimit-Remaining" in resp.headers

    # 4th should be blocked
    resp4 = client_a.post("/api/v1/links", json={"url": "https://example.com"})
    assert resp4.status_code == 429
    assert resp4.headers.get("X-RateLimit-Limit") == "3"
    assert "X-RateLimit-Remaining" in resp4.headers
    assert "Retry-After" in resp4.headers

def test_list_links_owner_only(client_a, client_b):
    client_a.post("/api/v1/links", json={"url": "https://example.com"})
    client_a.post("/api/v1/links", json={"url": "https://example.com/a"})

    la = client_a.get("/api/v1/links?limit=50")
    assert la.status_code == 200
    assert len(la.json()["items"]) == 2

    lb = client_b.get("/api/v1/links?limit=50")
    assert lb.status_code == 200
    assert len(lb.json()["items"]) == 0


def test_list_links_cursor_pagination(client_a):
    for i in range(3):
        r = client_a.post("/api/v1/links", json={"url": f"https://example.com/{i}"})
        assert r.status_code == 201

    p1 = client_a.get("/api/v1/links?limit=2").json()
    assert len(p1["items"]) == 2
    assert p1["next_cursor"] is not None

    p2 = client_a.get(f"/api/v1/links?limit=2&cursor={p1['next_cursor']}").json()
    assert len(p2["items"]) == 1
    assert p2["next_cursor"] is None


def test_patch_disable_link_owner_only(client_a, client_b):
    code = client_a.post("/api/v1/links", json={"url": "https://example.com"}).json()["code"]

    # B can't disable A's link
    bad = client_b.patch(f"/api/v1/links/{code}", json={"is_active": False})
    assert bad.status_code == 404

    # A disables
    ok = client_a.patch(f"/api/v1/links/{code}", json={"is_active": False})
    assert ok.status_code == 200
    assert ok.json()["is_active"] is False

    # redirect is now 403
    redir = client_a.get(f"/{code}", follow_redirects=False)
    assert redir.status_code == 403

def test_analytics_endpoint_returns_click_count_and_last_accessed_at(client_a):
    create = client_a.post("/api/v1/links", json={"url": "https://example.com"})
    assert create.status_code == 201
    code = create.json()["code"]

    a0 = client_a.get(f"/api/v1/links/{code}/analytics")
    assert a0.status_code == 200
    body0 = a0.json()
    assert body0["click_count"] == 0
    assert body0["last_accessed_at"] is None

    # one redirect click
    r = client_a.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 307

    a1 = client_a.get(f"/api/v1/links/{code}/analytics")
    assert a1.status_code == 200
    body1 = a1.json()
    assert body1["click_count"] == 1
    assert body1["last_accessed_at"] is not None


def test_analytics_owner_only_returns_404(client_a, client_b):
    create = client_a.post("/api/v1/links", json={"url": "https://example.com"})
    assert create.status_code == 201
    code = create.json()["code"]

    resp = client_b.get(f"/api/v1/links/{code}/analytics")
    assert resp.status_code == 404
