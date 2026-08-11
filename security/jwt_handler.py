import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import jwt

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

if SECRET_KEY is None:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set"
        )

ALGORITHM = os.getenv("ALGIRITHM","HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int (os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES",
                                             "30"))

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
