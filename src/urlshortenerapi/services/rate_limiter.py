from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from redis import Redis

@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_seconds: int

def check_rate_limit(
    r: Redis,
    key: str,
    limit: int,
    window_seconds: int,
) -> RateLimitResult:
    """
    Algorithm:
    - Increment key
    - If this is the first hit, set expiry window_seconds
    - If count > limit => block
    - remaining = max(0, limit - count)
    - reset_seconds from TTL (best-effort)
    """
    count = r.incr(key)

    if count == 1:
        # first request in the window; start the window timer
        r.expire(key, window_seconds)

    ttl = r.ttl(key)
    reset_seconds = ttl if isinstance(ttl, int) and ttl > 0 else window_seconds

    remaining = max(0, limit - int(count))
    allowed = int(count) <= limit

    return RateLimitResult(allowed=allowed, remaining=remaining, reset_seconds=reset_seconds)