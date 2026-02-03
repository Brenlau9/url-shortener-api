import os
import hashlib
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Set test-friendly rate limits BEFORE importing the app anywhere
os.environ.setdefault("REDIRECT_LIMIT", "3")
os.environ.setdefault("REDIRECT_WINDOW", "60")


def _hash_api_key(raw_key: str) -> str:
    # Must match urlshortenerapi.api.deps.hash_api_key
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


@pytest.fixture(scope="session")
def api_key_header() -> dict[str, str]:
    """
    Create a test API key row in the DB and return headers containing the plaintext key.

    IMPORTANT: The app stores only key_hash; tests keep the plaintext in memory to authenticate.
    """
    # Import here so env vars above are applied before settings load
    from urlshortenerapi.core.config import settings
    from urlshortenerapi.db.models import ApiKey

    raw_key = "sk_test_" + secrets.token_urlsafe(24)
    key_hash = _hash_api_key(raw_key)

    engine = create_engine(settings.database_url)

    # Insert api key if it doesn't already exist
    with Session(engine) as db:
        existing = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
        if existing is None:
            db.add(ApiKey(name="test", key_hash=key_hash))
            db.commit()

    return {"X-API-Key": raw_key}


@pytest.fixture()
def client(api_key_header: dict[str, str]) -> TestClient:
    """
    TestClient with X-API-Key set by default.
    """
    from urlshortenerapi.main import app

    c = TestClient(app)
    c.headers.update(api_key_header)
    return c
