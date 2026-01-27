import os
import redis

def get_redis_client() -> redis.Redis:
    """
    Creates a Redis client using REDIS_URL.
    decode_responses=True returns str instead of bytes.
    """
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return redis.Redis.from_url(redis_url, decode_responses=True)