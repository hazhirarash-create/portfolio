import os
import uuid

import pytest

from sqlalchemy import create_engine, text, delete
from sqlalchemy.orm import Session

from models.models import User, RefreshToken, RefreshTokenStatus
from security.jwt_handler import (
    create_refresh_token,
    decode_refresh_token,
)
from services.user_service import rotate_refresh_token, logout_refresh_session
from exceptions.auth_exceptions import RefreshTokenReuseDetectedError

@pytest.fixture
def pg_test_data():
    database_url = os.environ.get("PG_TEST_DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "PG_TEST_DATABASE_URL must be configured"
        )

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    user_id = None

    try:
        
        if engine.dialect.name != "postgresql":
            raise RuntimeError("PostgreSQL is required")

        with engine.connect() as connection:
            database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

            if database_name != "portfolio_test_db":
                raise RuntimeError(
                    f"Unsafe test database: {database_name}"
                )

            revision = connection.execute(
                text(
                    "SELECT version_num "
                    "FROM public.alembic_version"
                )
            ).scalar_one()

            if revision != "627a31e10de3":
                raise RuntimeError(
                    f"Unexpected revision: {revision}"
                )

        unique_id = uuid.uuid4().hex
        family_id = str(uuid.uuid4())

        
        with Session(engine) as db:
            user = User(
                username=f"pg_test_{unique_id}",
                email=f"pg_{unique_id}@example.invalid",
                hashed_password="test-only-hash",
                is_active=True,
                is_admin=False,
            )

            db.add(user)
            db.flush()

            user_id = user.id

            refresh_token, jti, expires_at = (
                create_refresh_token(
                    user_id=user_id,
                    family_id=family_id,
                )
            )

            token_record = RefreshToken(
                jti=jti,
                user_id=user_id,
                family_id=family_id,
                expires_at=expires_at,
                status=RefreshTokenStatus.ACTIVE,
            )

            db.add(token_record)
            db.commit()

        yield {
            "engine": engine,
            "user_id": user_id,
            "family_id": family_id,
            "token": refresh_token,
            "jti": jti,
        }

    finally:
        
        try:
            if user_id is not None:
                with Session(engine) as db:
                    db.query(RefreshToken).filter(
                        RefreshToken.user_id == user_id
                    ).delete(synchronize_session=False)

                    db.query(User).filter(
                        User.id == user_id
                    ).delete(synchronize_session=False)

                    db.commit()
        finally:
            engine.dispose()


def test_postgres_rotation_succeeds(pg_test_data):
    engine = pg_test_data["engine"]
    old_jti = pg_test_data["jti"]

    
    with Session(engine) as db:
        access_token, refresh_token = rotate_refresh_token(
            refresh_token=pg_test_data["token"],
            db=db,
        )

        assert access_token
        assert refresh_token
        assert not db.in_transaction()

    new_payload = decode_refresh_token(refresh_token)

    assert new_payload["jti"] != old_jti
    assert new_payload["family_id"] == pg_test_data["family_id"]

    
    with Session(engine) as db:
        old_record = db.query(RefreshToken).filter(
            RefreshToken.jti == old_jti
        ).one()

        new_record = db.query(RefreshToken).filter(
            RefreshToken.jti == new_payload["jti"]
        ).one()

        assert old_record.status == RefreshTokenStatus.USED
        assert old_record.used_at is not None

        assert new_record.status == RefreshTokenStatus.ACTIVE
        assert new_record.used_at is None

        assert new_record.family_id == pg_test_data["family_id"]
        assert new_record.user_id == pg_test_data["user_id"]

def test_postgres_reuse_revokes_active_family(pg_test_data):
    engine = pg_test_data["engine"]
    original_token = pg_test_data["token"]
    original_jti = pg_test_data["jti"]
    family_id = pg_test_data["family_id"]

    
    with Session(engine) as db:
        _, refresh_b = rotate_refresh_token(
            refresh_token=original_token,
            db=db,
        )

        assert not db.in_transaction()

    payload_b = decode_refresh_token(refresh_b)

    
    with Session(engine) as db:
        with pytest.raises(RefreshTokenReuseDetectedError):
            rotate_refresh_token(
                refresh_token=original_token,
                db=db,
            )

        assert not db.in_transaction()

    
    with Session(engine) as db:
        token_a = (
            db.query(RefreshToken)
            .filter(RefreshToken.jti == original_jti)
            .one()
        )

        token_b = (
            db.query(RefreshToken)
            .filter(RefreshToken.jti == payload_b["jti"])
            .one()
        )

        assert token_a.status == RefreshTokenStatus.USED
        assert token_a.used_at is not None
        assert token_a.revoked_at is None

        assert token_b.status == RefreshTokenStatus.REVOKED
        assert token_b.revoked_at is not None
        assert token_b.used_at is None

        assert token_b.family_id == family_id

        family_records = (
            db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id)
            .all()
        )

        assert len(family_records) == 2

        assert all(
            record.status != RefreshTokenStatus.ACTIVE
            for record in family_records
        )


def test_postgres_logout_revokes_active_token(pg_test_data):
    engine = pg_test_data["engine"]
    original_token = pg_test_data["token"]
    original_jti = pg_test_data["jti"]

    with Session(engine) as db:
        logout_refresh_session(
            refresh_token=original_token,
            db=db,
        )

        assert not db.in_transaction()

    with Session(engine) as db:
        token_record = (
            db.query(RefreshToken)
            .filter(RefreshToken.jti == original_jti)
            .one()
        )

        assert token_record.status == RefreshTokenStatus.REVOKED
        assert token_record.revoked_at is not None
        assert token_record.used_at is None

        family_records = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.family_id == pg_test_data["family_id"]
            )
            .all()
        )

        assert len(family_records) == 1

        assert all(
            record.status != RefreshTokenStatus.ACTIVE
            for record in family_records
        )

def test_postgres_logout_is_idempotent(pg_test_data):

    engine = pg_test_data["engine"]
    token = pg_test_data["token"]
    jti = pg_test_data["jti"]

    with Session(engine) as db:
        logout_refresh_session(
            refresh_token=token,
            db=db,
        )

        assert not db.in_transaction()

    with Session(engine) as db:
        token_record = (
            db.query(RefreshToken)
            .filter(RefreshToken.jti == jti)
            .one()
        )

        assert token_record.status == RefreshTokenStatus.REVOKED
        assert token_record.revoked_at is not None
        assert token_record.used_at is None

        first_revoked_at = token_record.revoked_at

    with Session(engine) as db:
        logout_refresh_session(
            refresh_token=token,
            db=db,
        )

        assert not db.in_transaction()

    with Session(engine) as db:
        token_record = (
            db.query(RefreshToken)
            .filter(RefreshToken.jti == jti)
            .one()
        )

        assert token_record.status == RefreshTokenStatus.REVOKED
        assert token_record.revoked_at == first_revoked_at
        assert token_record.used_at is None
