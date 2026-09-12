from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
from exceptions.user_exceptions import (InvalidTokenError,
                             InactiveUserError,
                             AdminAccessRequiredError)
from models.models import User
from security.jwt_handler import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/users/login"
)

def get_current_user(
        token : str = Depends(oauth2_scheme),
        db : Session = Depends(get_db)
) -> User :

    user_id = decode_access_token(token)

    user = db.query(User).filter_by(id = user_id).first()

    if user is None:
        raise InvalidTokenError()

    if not user.is_active:
        raise InactiveUserError()

    return user


def get_current_admin_user(
        current_user : User = Depends(get_current_user)
) -> User:

    if not current_user.is_admin:
        raise AdminAccessRequiredError()

    return current_user