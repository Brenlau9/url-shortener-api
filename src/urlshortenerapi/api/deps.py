from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from redis import Redis

from urlshortenerapi.core.redis import get_redis_client
from urlshortenerapi.services.rate_limiter import check_rate_limit, check_token_bucket

import os

import hashlib
import secrets
from fastapi import Header
from sqlalchemy.orm import Session

from urlshortenerapi.db.session import get_db
from urlshortenerapi.db.models import ApiKey


REDIRECT_LIMIT = int(os.getenv("REDIRECT_LIMIT", "60"))
REDIRECT_WINDOW = int(os.getenv("REDIRECT_WINDOW", "60"))


def get_client_ip(request: Request) -> str:
    # Simple local-dev safe approach.
    # If behind a proxy in real deployments, you'd use X-Forwarded-For carefully.
    return request.client.host if request.client else "unknown"


def redirect_rate_limiter(
    request: Request,
    r: Redis = Depends(get_redis_client),
) -> None:
    ip = get_client_ip(request)
    key = f"rl:redirect:{ip}"

    result = check_rate_limit(r, key=key, limit=REDIRECT_LIMIT, window_seconds=REDIRECT_WINDOW)

    # Optional: include headers so clients can see remaining + reset
    request.state.rate_limit_remaining = result.remaining
    request.state.rate_limit_reset = result.reset_seconds

    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {result.reset_seconds}s.",
        )

def hash_api_key(raw_key: str) -> str:
    # SHA-256 hex digest (64 chars)
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def get_current_api_key(
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> ApiKey:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key")

    key_hash = hash_api_key(x_api_key)

    api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
    if api_key is None:
        # Do not reveal whether a key exists; same error for missing/invalid
        raise HTTPException(status_code=401, detail="Invalid API key")

    return api_key

def create_rate_limiter(
    request: Request,
    api_key: ApiKey = Depends(get_current_api_key),
    r: Redis = Depends(get_redis_client),
) -> None:
    """
    Per-API-key token bucket limiter for POST /api/v1/links.
    Runtime env read so tests and deployments can change limits without reload.
    """
    create_limit = int(os.getenv("CREATE_LIMIT", "60"))
    create_window = int(os.getenv("CREATE_WINDOW", "60"))

    key = f"rate:create:{api_key.id}"

    result = check_token_bucket(
        r,
        key=key,
        capacity=create_limit,
        window_seconds=create_window,
        cost=1,
        ttl_seconds=create_window * 2,
    )

    # Store for route to set headers on success
    request.state.create_rl_limit = create_limit
    request.state.create_rl_remaining = result.remaining
    request.state.create_rl_retry_after = result.retry_after

    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many create requests. Try again in {result.retry_after} seconds.",
            headers={
                "Retry-After": str(result.retry_after),
                "X-RateLimit-Limit": str(create_limit),
                "X-RateLimit-Remaining": str(result.remaining),
            },
        )

