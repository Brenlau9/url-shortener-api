from __future__ import annotations
from dataclasses import dataclass

from redis import Redis
import time


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


TOKEN_BUCKET_LUA = r"""
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

local data = redis.call("HMGET", key, "tokens", "ts")
local tokens = tonumber(data[1])
local ts = tonumber(data[2])

if tokens == nil then tokens = capacity end
if ts == nil then ts = now end

-- refill tokens based on elapsed time
local delta = math.max(0, now - ts)
tokens = math.min(capacity, tokens + (delta * refill_rate))

local allowed = 0
local retry_after = 0

if tokens >= cost then
  allowed = 1
  tokens = tokens - cost
else
  allowed = 0
  retry_after = math.ceil((cost - tokens) / refill_rate)
end

redis.call("HMSET", key, "tokens", tokens, "ts", now)
redis.call("EXPIRE", key, ttl)

return {allowed, tokens, retry_after}
"""


@dataclass(frozen=True)
class TokenBucketResult:
    allowed: bool
    remaining: int
    retry_after: int


def check_token_bucket(
    r: Redis,
    key: str,
    capacity: int,
    window_seconds: int,
    cost: int = 1,
    ttl_seconds: int | None = None,
) -> TokenBucketResult:
    """
    Token bucket:
    - capacity tokens
    - refills linearly: capacity / window_seconds tokens per second
    - each request costs 'cost'
    - retry_after tells client when 1 token will be available

    Uses Redis Lua for atomicity.
    """
    refill_rate = capacity / float(window_seconds)
    now = time.time()
    ttl = ttl_seconds if ttl_seconds is not None else window_seconds * 2

    allowed, tokens, retry_after = r.eval(
        TOKEN_BUCKET_LUA,
        1,
        key,
        capacity,
        refill_rate,
        now,
        cost,
        ttl,
    )

    # redis-py may return ints/floats; be defensive
    allowed_bool = bool(int(allowed))
    remaining_int = max(0, int(float(tokens)))
    retry_int = int(retry_after)

    return TokenBucketResult(allowed=allowed_bool, remaining=remaining_int, retry_after=retry_int)
