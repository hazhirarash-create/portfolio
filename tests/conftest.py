import pytest
from pytest import MonkeyPatch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid
from database import Base
import models.models
from models.models import User, RefreshToken, RefreshTokenStatus
from security.jwt_handler import create_refresh_token



@pytest.fixture
def db_session(tmp_path):
    database_path = tmp_path / "test_portfolio.db"

    test_engine = create_engine(
        f"sqlite:///{database_path}",
        echo=False,
    )

    try:
        Base.metadata.create_all(bind=test_engine)

        TestSessionLocal = sessionmaker(bind=test_engine)
        db = TestSessionLocal()

        try:
            yield db
        finally:
            db.close()

    finally:
        test_engine.dispose()


@pytest.fixture
def test_user(db_session):
    user = User(
        username="rotation_test_user",
        email="rotation_test@example.com",
        hashed_password="not-a-real-password-hash",
        is_active=True,
        is_admin=False,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user

@pytest.fixture
def active_refresh_token(db_session, test_user):
    family_id = str(uuid.uuid4())

    token, jti, expires_at = create_refresh_token(
        user_id=test_user.id,
        family_id=family_id,
    )

    token_record = RefreshToken(
        jti=jti,
        user_id=test_user.id,
        family_id=family_id,
        expires_at=expires_at,
        status=RefreshTokenStatus.ACTIVE,
    )

    db_session.add(token_record)
    db_session.commit()

    return {
        "token": token,
        "jti": jti,
        "family_id": family_id,
    }

def fail_create_refresh_token(user_id, family_id):
    raise RuntimeError("Simulated refresh creation failure")

