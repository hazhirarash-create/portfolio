from asyncio.log import logger
from sqlalchemy import update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.models import User, RefreshToken, RefreshTokenStatus
from schemas.user import UserCreate, UserLogin
from security.password import (hash_password,
                               DUMMY_PASSWORD_HASH,
                               verify_password)
from exceptions.user import (CompromisedPasswordError, UsernameAlreadyExistsError,
                            EmailAlreadyExistsError,
                            UserAlreadyExistsError,
                            InvalidCredentialsError,
                            InactiveUserError,
                            CompromisedPasswordError,
                            InvalidTokenError,
                            RefreshTokenReuseDetectedError)
from security.password_breach import check_pwned_password
import logging
from security.jwt_handler import (decode_refresh_token,
                                  create_access_token,
                                  create_refresh_token)
from datetime import datetime, timezone
import uuid

logger = logging.getLogger(__name__)

def get_user_by_username(username:str,
                         db:Session
                         ) -> User | None:
    return(db.query(User)
           .filter_by(username=username)
           .first()
           )

def get_user_by_email(email:str,
                      db:Session
                      ) -> User | None:
    return (db.query(User)
            .filter_by(email=email)
            .first()
            ) 

def get_refresh_token_by_jti(jti: str,
                             db: Session
                             ) -> RefreshToken | None:  
    return (db.query(RefreshToken)
            .filter(RefreshToken.jti == jti)
            .first()
            ) 

def revoke_token_family(
    family_id: str,
    db: Session,
) -> None:
    now = datetime.now(timezone.utc)

    active_tokens = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.family_id == family_id,
            RefreshToken.status == RefreshTokenStatus.ACTIVE,
        )
        .all()
    )

    for token in active_tokens:
        token.status = RefreshTokenStatus.REVOKED
        token.revoked_at = now

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

def rotate_refresh_token(
        refresh_token: str,
        db: Session
        ) -> tuple[str, str]: 

    payload = decode_refresh_token(refresh_token)
    
    token_record = get_refresh_token_by_jti(
        jti=payload["jti"],
        db=db
    )

    if token_record is None:
        raise InvalidTokenError()

    if token_record.user_id != payload["user_id"]:
        raise InvalidTokenError()

    if token_record.family_id != payload["family_id"]:
        raise InvalidTokenError()

    if token_record.status == RefreshTokenStatus.REVOKED:
        raise InvalidTokenError()

    if token_record.status == RefreshTokenStatus.USED:
        revoke_token_family(
            family_id=token_record.family_id,
            db=db
        )
        try:
            db.commit()
        except Exception:
            db.rollback()
        raise RefreshTokenReuseDetectedError()

    logger.warning(
    "Refresh token reuse detected family_id=%s",
    token_record.family_id,
    )

    if token_record.status != RefreshTokenStatus.ACTIVE:
        raise InvalidTokenError()

    now = datetime.now(timezone.utc)

    stmt = (update(RefreshToken)
            .where(
                RefreshToken.id == token_record.id,
                RefreshToken.status == RefreshTokenStatus.ACTIVE)
            .values(
                status = RefreshTokenStatus.USED,
                used_at = now)
                )
    result = db.execute(stmt)

    if result.rowcount != 1:
        db.rollback()

        current_record = get_refresh_token_by_jti(
            jti=payload["jti"],
            db=db
        )

        if current_record is None:
            raise InvalidTokenError()

        if current_record.status == RefreshTokenStatus.USED:
            revoke_token_family(
                family_id=current_record.family_id,
                db=db
            )

            try:
                db.commit()
            except Exception:
                db.rollback()
                raise

            raise RefreshTokenReuseDetectedError()
        
        raise InvalidTokenError()

    if result.rowcount == 1:
        new_access_token = create_access_token(
            user_id=token_record.user_id
        )

        (
            new_refresh_token,
            new_jti,
            new_expires_at,
        ) = create_refresh_token(
            user_id=token_record.user_id,
            family_id=token_record.family_id,
        )

        new_refresh_record = RefreshToken(
            jti=new_jti,
            user_id=token_record.user_id,
            family_id=token_record.family_id,
            expires_at=new_expires_at,
            status=RefreshTokenStatus.ACTIVE,
        )

        db.add(new_refresh_record)

        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

        return (
            new_access_token,
            new_refresh_token,
        )

def create_login_tokens(
        user_id: int,
        db: Session
) -> tuple[str, str]:
    
    family_id = str(uuid.uuid4())

    access_token = create_access_token(user_id=user_id)

    (refresh_token, jti, expires_at) = create_refresh_token(
        user_id=user_id,
        family_id=family_id
    )

    refresh_record = RefreshToken(
        jti=jti,
        user_id=user_id,
        family_id=family_id,
        expires_at=expires_at,
        status=RefreshTokenStatus.ACTIVE
    )

    db.add(refresh_record)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return(access_token,
           refresh_token)