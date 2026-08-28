import redis
import time
import uuid
import logging

from fastapi import HTTPException, Request, status

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)

logger = logging.getLogger(__name__)

MAX_REQUESTS = 5
WINDOW_SECONDS = 60

RATE_LIMIT_SCRIPT = """
local key = KEYS[1]

local window_start = tonumber(ARGV[1])
local current_time = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local unique_member = ARGV[4]
local ttl = tonumber(ARGV[5])

redis.call(
    "ZREMRANGEBYSCORE",
    key,
    "-inf",
    "(" .. window_start
)

local current_count = redis.call(
    "ZCARD",
    key
)

if current_count >= max_requests then
    return 0
end

redis.call(
    "ZADD",
    key,
    current_time,
    unique_member
)

redis.call(
    "EXPIRE",
    key,
    ttl
)

return 1
"""

rate_limit_script = redis_client.register_script(
    RATE_LIMIT_SCRIPT
)

def check_rate_limit(request: Request) -> None:
    client_ip = request.client.host
    key = f"login_rate_limit:{client_ip}"

    current_time = time.time()
    window_start = current_time - WINDOW_SECONDS
    unique_member = str(uuid.uuid4())
    try:
        result = rate_limit_script(
            keys=[key],
            args=[
                window_start,
                current_time,
                MAX_REQUESTS,
                unique_member,
                WINDOW_SECONDS,
            ]
        )
    except redis.RedisError:
        logger.warning(
            "Redis unavailable during login rate limiting",
            exc_info=True
        )
        return 
    
    if result == 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )