import redis
import os
import json

redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))

def get_cached_url(short_code: str):
    data = redis_client.get(short_code)
    if data:
        return json.loads(data)
    return None

def set_cached_url(short_code: str, url_data: dict, ex: int = 3600):
    redis_client.setex(short_code, ex, json.dumps(url_data))