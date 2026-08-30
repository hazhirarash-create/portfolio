from datetime import datetime, timedelta, timezone
import jwt
from exceptions.user import InvalidTokenError
from core.config import (ACCESS_TOKEN_EXPIRE_MINUTES,
                         SECRET_KEY,
                         ALGORITHM)


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