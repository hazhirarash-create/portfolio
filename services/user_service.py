from asyncio.log import logger

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.models import User
from schemas.user import UserCreate, UserLogin
from security.password import (hash_password,
                               DUMMY_PASSWORD_HASH,
                               verify_password)
from exceptions.user import (CompromisedPasswordError, UsernameAlreadyExistsError,
                            EmailAlreadyExistsError,
                            UserAlreadyExistsError,
                            InvalidCredentialsError,
                            InactiveUserError,
                            CompromisedPasswordError)
from security.password_breach import check_pwned_password
import logging

logger = logging.getLogger(__name__)

def get_user_by_username(username:str,
                         db:Session
                         ) -> User | None:
    return(db.query(User).filter_by(username=username).first())

def get_user_by_email(email:str,
                      db:Session
                      ) -> User | None:
    return (db.query(User).filter_by(email=email).first()) 
    

def create_user(
    user_data: UserCreate,
    db: Session
) -> User:

    existing_username = get_user_by_username(username=user_data.username,
                                             db=db)

    if existing_username is not None:
        raise UsernameAlreadyExistsError(user_data.username)

    existing_email = get_user_by_email(email=user_data.email,
                                       db=db)
    if existing_email is not None:
        raise EmailAlreadyExistsError(user_data.email)

    pwned_password = check_pwned_password(user_data.password)

    if pwned_password is True:
        raise CompromisedPasswordError()
    
    hashed_password = hash_password(user_data.password)

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

    except IntegrityError as exc:
        db.rollback()
        raise UserAlreadyExistsError() from exc

    except Exception:
        db.rollback()
        raise

    return new_user


def authenticate_user(
        user_data : UserLogin,
        db : Session
        ) -> User:
    
    user = get_user_by_username(
        username=user_data.username,
        db=db
    )
    if user is None:
        verify_password(plain_password=user_data.password,
                        hashed_password=DUMMY_PASSWORD_HASH
    )
        logger.warning("Login failed: user not found")

        raise InvalidCredentialsError()

    password_is_valid = verify_password(
        plain_password=user_data.password,
        hashed_password=user.hashed_password
    )

    if not password_is_valid:
        logger.warning("Login failed: invalid password")
        raise InvalidCredentialsError()

    if not user.is_active:
        logger.warning("Login failed: inactive user")
        raise InactiveUserError()

    logger.info(
        "User login successful user_id=%s",
        user.id
    )

    return user