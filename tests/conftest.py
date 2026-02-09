import os
import hashlib
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from urlshortenerapi.main import app
from urlshortenerapi.api.deps import redirect_rate_limiter
from urlshortenerapi.core.redis import get_redis_client


os.environ.setdefault("REDIRECT_LIMIT", "3")
os.environ.setdefault("REDIRECT_WINDOW", "60")


def _hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _ensure_api_key(name: str, raw_key: str) -> None:
    from urlshortenerapi.core.config import settings
    from urlshortenerapi.db.models import ApiKey

    engine = create_engine(settings.database_url)
    key_hash = _hash_api_key(raw_key)

    with Session(engine) as db:
        existing = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
        if existing is None:
            db.add(ApiKey(name=name, key_hash=key_hash))
            db.commit()


@pytest.fixture(scope="session")
def api_key_a() -> str:
    raw = "sk_test_a_" + secrets.token_urlsafe(24)
    _ensure_api_key("test-a", raw)
    return raw


@pytest.fixture(scope="session")
def api_key_b() -> str:
    raw = "sk_test_b_" + secrets.token_urlsafe(24)
    _ensure_api_key("test-b", raw)
    return raw


@pytest.fixture(autouse=True)
def isolate_db():
    """
    Full test isolation:
    - Wipe links table before each test
    - Clear Redis rate limiter keys so POST /links doesn't randomly 429
    """
    from urlshortenerapi.core.config import settings

    # --- DB isolation ---
    engine = create_engine(settings.database_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE links RESTART IDENTITY CASCADE;"))

    # --- Redis isolation ---
    r = get_redis_client()
    # remove create limiter keys (per API key)
    for k in r.scan_iter("rate:create:*"):
        r.delete(k)
    # (optional) if you want redirect limiter isolated too:
    for k in r.scan_iter("rl:redirect:*"):
        r.delete(k)

    yield


@pytest.fixture()
def client_a(api_key_a: str) -> TestClient:
    # Override redirect rate limiter for determinism in redirect tests
    app.dependency_overrides[redirect_rate_limiter] = lambda: None

    c = TestClient(app)
    c.headers.update({"X-API-Key": api_key_a})
    return c


@pytest.fixture()
def client_b(api_key_b: str) -> TestClient:
    app.dependency_overrides[redirect_rate_limiter] = lambda: None

    c = TestClient(app)
    c.headers.update({"X-API-Key": api_key_b})
    return c
