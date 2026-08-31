import redis
import uuid
import logging

from fastapi import HTTPException, Request, status
from core.config import (REDIS_HOST,
                         REDIS_PORT,
                         REDIS_CONNECT_TIMEOUT,
                         REDIS_SOCKET_TIMEOUT)

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
    socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
    socket_timeout=REDIS_SOCKET_TIMEOUT
)

logger = logging.getLogger(__name__)

MAX_REQUESTS = 5
WINDOW_SECONDS = 60

RATE_LIMIT_SCRIPT = """
local key = KEYS[1]

local max_requests = tonumber(ARGV[1])
local unique_member = ARGV[2]
local ttl = tonumber(ARGV[3])

local redis_time = redis.call("TIME")

local seconds = tonumber(redis_time[1])
local microseconds = tonumber(redis_time[2])

local current_time =
    seconds + (microseconds / 1000000)

local window_start =
    current_time - ttl

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
    local oldest_entry = redis.call(
        "ZRANGE",
        key,
        0,
        0,
        "WITHSCORES"
    )

    local oldest_score = tonumber(
        oldest_entry[2]
    )

    local retry_after = math.ceil(
        (oldest_score + ttl) - current_time
    )

    return {
        0,
        retry_after
    }
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

return {
    1,
    0}
"""

rate_limit_script = redis_client.register_script(
    RATE_LIMIT_SCRIPT
)

def check_rate_limit(request: Request) -> None:
    client_ip = request.client.host
    key = f"login_rate_limit:{client_ip}"

    unique_member = str(uuid.uuid4())
    try:
        result = rate_limit_script(
            keys=[key],
            args=[
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
    allowed = result[0]
    retry_after = result[1]

    if allowed == 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many login attempts. "
                "Please try again later."
            ),
            headers={
                "Retry-After": str(retry_after)
            }
        )
        
    if result == 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )