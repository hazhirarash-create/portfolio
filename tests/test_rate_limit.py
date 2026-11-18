
import logging
import uuid

import redis
from security.rate_limit import (
    redis_client,
    rate_limit_script,
    MAX_REQUESTS,
    WINDOW_SECONDS,
)

import pytest
from fastapi import HTTPException
from starlette.requests import Request
import security.rate_limit as rate_limit_module

def test_rate_limit_allows_five_requests_and_rejects_sixth():
    key = f"test:login_rate_limit:{uuid.uuid4()}"

    try:
        for _ in range(MAX_REQUESTS):
            result = rate_limit_script(
                keys=[key],
                args=[
                    MAX_REQUESTS,
                    str(uuid.uuid4()),
                    WINDOW_SECONDS,
                ],
            )

            assert result[0] == 1
            assert result[1] == 0

        result = rate_limit_script(
            keys=[key],
            args=[
                MAX_REQUESTS,
                str(uuid.uuid4()),
                WINDOW_SECONDS,
            ],
        )

        assert result[0] == 0

        retry_after = result[1]

        assert isinstance(retry_after, int)
        assert 1 <= retry_after <= WINDOW_SECONDS

    finally:
        redis_client.delete(key)

def test_check_rate_limit_returns_429_with_retry_after(
        monkeypatch
):

    def mock_rate_limit_script(keys, args):
        return [0, 42]

    monkeypatch.setattr(
        rate_limit_module,
        "rate_limit_script",
        mock_rate_limit_script
    )

    request = Request(
        {
            "type": "http",
            "client": ("192.0.2.10", 12345),
            "method": "POST",
            "path": "/users/login",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
            "http_version": "1.1",
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        rate_limit_module.check_rate_limit(request)

    exception = exc_info.value

    assert exception.status_code == 429

    assert exception.headers["Retry-After"] == "42"

    assert exception.detail == (
        "Too many login attempts. "
        "Please try again later."
    )


def test_login_endpoint_returns_429_with_retry_after(
    http_client,
    monkeypatch,
):

    def fake_rate_limit_script(keys, args):
        return [0, 42]

    monkeypatch.setattr(
        rate_limit_module,
        "rate_limit_script",
        fake_rate_limit_script,
    )

    response = http_client.post(
        "/users/login",
        data={
            "username": "rate_limited_user",
            "password": "SomePassword_2026!Q7",
        },
    )

    assert response.status_code == 429, response.text

    assert response.headers.get("Retry-After") == "42"

    assert response.json() == {
        "detail": (
            "Too many login attempts. "
            "Please try again later."
        )
    }


def test_check_rate_limit_fails_open_when_redis_unavailable(
    monkeypatch,
    caplog,
):
    def fake_rate_limit_script(keys, args):
        raise redis.exceptions.ConnectionError(
            "Simulated Redis connection failure"
        )

    monkeypatch.setattr(
        rate_limit_module,
        "rate_limit_script",
        fake_rate_limit_script,
    )

    request = Request(
        {
            "type": "http",
            "client": ("192.0.2.10", 12345),
            "method": "POST",
            "path": "/users/login",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
            "http_version": "1.1",
        }
    )

    with caplog.at_level(
        logging.WARNING,
        logger=rate_limit_module.__name__,
    ):
        result = rate_limit_module.check_rate_limit(
            request
        )

    assert result is None

    assert (
        "Redis unavailable during login rate limiting"
        in caplog.text
    )


def test_rate_limit_removes_expired_requests():

    key = f"test:expired_rate_limit:{uuid.uuid4()}"

    try:
        seconds, microseconds = redis_client.time()

        current_time = seconds + microseconds / 1_000_000

        old_timestamp = current_time - WINDOW_SECONDS - 10

        redis_client.zadd(
            key,
            {
                "expired-request": old_timestamp,
            },
        )

        result = rate_limit_script(
            keys=[key],
            args=[
                MAX_REQUESTS,
                str(uuid.uuid4()),
                WINDOW_SECONDS,
            ],
        )

        assert result[0] == 1
        assert result[1] == 0

        remaining_members = redis_client.zrange(
            key,
            0,
            -1,
        )

        assert "expired-request" not in remaining_members
        assert len(remaining_members) == 1

    finally:
        redis_client.delete(key)


def test_rate_limit_window_boundary_is_inclusive():

    key = f"test:rate_limit_boundary:{uuid.uuid4()}"

    try:
        window_start = 60.0

        redis_client.zadd(
            key,
            {
                "before-boundary": 59.999,
                "exact-boundary": 60.0,
                "after-boundary": 60.001,
            },
        )

        removed_count = redis_client.zremrangebyscore(
            key,
            "-inf",
            window_start,
        )

        assert removed_count == 2

        remaining_members = redis_client.zrange(
            key,
            0,
            -1,
        )

        assert remaining_members == [
            "after-boundary",
        ]

    finally:
        redis_client.delete(key)

