from datetime import datetime, timedelta, timezone
import jwt
from exceptions.auth_exceptions import InvalidTokenError
from core.config import (ACCESS_TOKEN_EXPIRE_MINUTES,
                         SECRET_KEY,
                         ALGORITHM,
                         REFRESH_TOKEN_EXPIRE_DAYS)
import uuid


def create_access_token(user_id: int) -> str:

    expire = (
        datetime.now(timezone.utc)
        + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        "sub": str(user_id),
        "exp": expire
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token


def decode_access_token(token : str) -> int:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        subject = payload.get("sub")

        if subject is None:
            raise InvalidTokenError()

        user_id = int(subject)

        return user_id
    
    except jwt.PyJWTError as exc:
        raise InvalidTokenError() from exc

    except ValueError as exc:
        raise InvalidTokenError() from exc

def create_refresh_token(
        user_id: int,
        family_id: str
) -> tuple[str, str, datetime]:

    jti = str(uuid.uuid4())

    expire_at = (
        datetime.now(timezone.utc)
        + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )

    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": jti,
        "family_id": family_id,
        "exp": expire_at
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token, jti, expire_at

def decode_refresh_token(token:str) -> dict:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        token_type = payload.get("type")
        subject = payload.get("sub")
        jti = payload.get("jti")
        family_id = payload.get("family_id")

        if token_type != "refresh":
            raise InvalidTokenError

        if subject is None:
            raise InvalidTokenError

        if jti is None:
            raise InvalidTokenError

        if family_id is None:
            raise InvalidTokenError

        user_id = int(subject)

        return {
            "user_id": user_id,
            "jti": jti,
            "family_id": family_id
        }

    except jwt.PyJWTError as exc:
        raise InvalidTokenError() from exc

    except ValueError as exc:
        raise InvalidTokenError() from exc