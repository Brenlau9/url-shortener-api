from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from redis import Redis

from urlshortenerapi.core.redis import get_redis_client
from urlshortenerapi.services.rate_limiter import check_rate_limit

import os

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
