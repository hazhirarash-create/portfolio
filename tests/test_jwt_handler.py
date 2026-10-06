import jwt
import pytest

from core.config import ALGORITHM, SECRET_KEY
from exceptions.auth_exceptions import InvalidTokenError
from security.jwt_handler import (
    create_access_token,
    decode_access_token,
    create_refresh_token,
    decode_refresh_token
)
from datetime import datetime, timedelta, timezone


def test_decode_access_token_successful():

    token = create_access_token(user_id = 1)
    user_id = decode_access_token(token)
    assert user_id == 1

def test_access_token_without_exp_is_rejected():

    token = jwt.encode(
        {
        "sub": "1",
        "type": "access"
        },
        SECRET_KEY,
        algorithm= ALGORITHM
        )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)

def test_access_token_without_sub_is_rejected():

    token = jwt.encode(
        {"type": "access",
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)
         },
         SECRET_KEY,
         algorithm= ALGORITHM
        )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)

def test_access_token_without_type_is_rejected():

    token = jwt.encode(
        {"sub": "1",
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)
         },
         SECRET_KEY,
         algorithm= ALGORITHM
         )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)

def test_access_token_with_refresh_type():

    token = jwt.encode(
        {"sub": "1",
         "type": "refresh",
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)
         },
         SECRET_KEY,
         algorithm= ALGORITHM
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)

def test_access_token_with_empty_sub_is_rejected():

    token = jwt.encode(
        {
            "sub": "",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm= ALGORITHM
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)

def test_access_token_with_invalid_sub_value_is_rejected():

    token = jwt.encode(
        {"sub": "abc",
         "type": "access",
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)
         },
         SECRET_KEY,
         algorithm= ALGORITHM
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)

def test_decode_refresh_token_successful():

    token, jti, _ = create_refresh_token(
        user_id=1,
        family_id="family-1",
    )

    payload = decode_refresh_token(token)

    assert payload["user_id"] == 1
    assert payload["jti"] == jti
    assert payload["family_id"] == "family-1"

def test_refresh_token_without_exp_is_rejected():

    token = jwt.encode(
        {"sub": "1",
         "family_id": "family-1",
         "type": "refresh",
         "jti": "jti-1"
         },
         SECRET_KEY,
         algorithm= ALGORITHM
    )

    with pytest.raises(InvalidTokenError):
        decode_refresh_token(token)

def test_refresh_token_without_sub_is_rejected():

    token = jwt.encode(
        {"family_id": "family-1",
         "exp": datetime.now(timezone.utc) + timedelta(days=7),
         "type": "refresh",
         "jti": "jti-1"
         },
         SECRET_KEY,
         algorithm= ALGORITHM
    )

    with pytest.raises(InvalidTokenError):
        decode_refresh_token(token)

def test_refresh_token_without_type_is_rejected():

    token = jwt.encode(
        {"sub": "1",
         "family_id": "family-1",
         "exp": datetime.now(timezone.utc) + timedelta(days=7),
         "jti": "jti-1"},
         SECRET_KEY,
         algorithm= ALGORITHM
    )

    with pytest.raises(InvalidTokenError):
        decode_refresh_token(token)

def test_refresh_token_with_invalid_type_value_is_rejected():

    token = jwt.encode(
        {"sub": "1",
         "exp": datetime.now(timezone.utc) + timedelta(days=7),
         "type": "access",
         "jti": "jti-1",
         "family_id": "family-1"},
         SECRET_KEY,
         algorithm= ALGORITHM
    )

    with pytest.raises(InvalidTokenError):
        decode_refresh_token(token)

def test_refresh_token_without_jti_is_rejected():

    token = jwt.encode(
        {"sub": "1",
         "exp": datetime.now(timezone.utc) + timedelta(days=7),
         "family_id": "family-1",
         "type": "refresh"},
         SECRET_KEY,
         algorithm= ALGORITHM
    )

    with pytest.raises(InvalidTokenError):
        decode_refresh_token(token)

def test_refresh_token_without_family_id_is_rejected():

    token = jwt.encode(
        {"sub": "1",
         "jti": "jti-1",
         "exp": datetime.now(timezone.utc) + timedelta(days=7),
         "type": "refresh"},
         SECRET_KEY,
         algorithm= ALGORITHM
    )

    with pytest.raises(InvalidTokenError):
        decode_refresh_token(token)

def test_refresh_token_with_empty_jti_is_rejected():

    token = jwt.encode(
        {
            "sub": "1",
            "type": "refresh",
            "jti": "",
            "family_id": "family-1",
            "exp": datetime.now(timezone.utc) + timedelta(days=7),
        },
        SECRET_KEY,
        algorithm= ALGORITHM,
    )

    with pytest.raises(InvalidTokenError):
        decode_refresh_token(token)

def test_refresh_token_with_empty_family_id_is_rejected():

    token = jwt.encode(
        {
            "sub": "1",
            "type": "refresh",
            "jti": "jti-1",
            "family_id": "",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    with pytest.raises(InvalidTokenError):
        decode_refresh_token(token)

def test_refresh_token_with_empty_sub_is_rejected():

    token = jwt.encode(
        {
            "sub": "",
            "type": "refresh",
            "jti": "jti-1",
            "family_id": "family-1",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    with pytest.raises(InvalidTokenError):
        decode_refresh_token(token)

def test_refresh_token_with_invalid_sub_value_is_rejected():

    token = jwt.encode(
        {
            "sub": "abc",
            "type": "refresh",
            "jti": "jti-1",
            "family_id": "family-1",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    with pytest.raises(InvalidTokenError):
        decode_refresh_token(token)

def test_expired_access_token_is_rejected():

    token = jwt.encode(
        {
            "sub": "1",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1)
            },
            SECRET_KEY,
            algorithm= ALGORITHM
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)

def test_expired_refresh_token_is_rejected():

    token = jwt.encode(
        {
            "sub": "1",
            "jti": "jti-1",
            "family_id": "family-1",
            "type": "refresh",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1)
        },
        SECRET_KEY,
        algorithm= ALGORITHM
        )

    with pytest.raises(InvalidTokenError):
        decode_refresh_token(token)