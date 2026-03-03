import os
from typing import Optional

import redis


_client: Optional[redis.Redis] = None


def get_redis() -> Optional[redis.Redis]:
    """Return a Redis client if REDIS_URL is set, otherwise None.

    This keeps local/dev setups working without Redis.
    """
    global _client
    if _client is not None:
        return _client

    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        return None

    # decode_responses=True gives us str instead of bytes
    _client = redis.from_url(url, decode_responses=True)
    return _client