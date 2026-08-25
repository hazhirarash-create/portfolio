import redis

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)

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