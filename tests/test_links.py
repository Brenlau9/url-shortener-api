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
