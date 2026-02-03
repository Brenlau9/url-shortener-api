import os
import hashlib
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Set test-friendly rate limits BEFORE importing the app/settings anywhere
os.environ.setdefault("REDIRECT_LIMIT", "3")
os.environ.setdefault("REDIRECT_WINDOW", "60")


def _hash_api_key(raw_key: str) -> str:
    # Must match urlshortenerapi.api.deps.hash_api_key
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _ensure_api_key_in_db(name: str, raw_key: str) -> None:
    """
    Insert an ApiKey row for raw_key (store only the hash). Safe to call repeatedly.
    """
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
    _ensure_api_key_in_db("test-a", raw)
    return raw


@pytest.fixture(scope="session")
def api_key_b() -> str:
    raw = "sk_test_b_" + secrets.token_urlsafe(24)
    _ensure_api_key_in_db("test-b", raw)
    return raw


@pytest.fixture()
def client_a(api_key_a: str) -> TestClient:
    from urlshortenerapi.main import app

    c = TestClient(app)
    c.headers.update({"X-API-Key": api_key_a})
    return c


@pytest.fixture()
def client_b(api_key_b: str) -> TestClient:
    from urlshortenerapi.main import app

    c = TestClient(app)
    c.headers.update({"X-API-Key": api_key_b})
    return c
