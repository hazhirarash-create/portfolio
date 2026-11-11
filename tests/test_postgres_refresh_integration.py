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

from services import user_service
from services.user_service import rotate_refresh_token, logout_refresh_session
from exceptions.auth_exceptions import RefreshTokenReuseDetectedError
from exceptions.auth_exceptions import InactiveUserError, InvalidTokenError
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from threading import Event

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

def test_postgres_logout_with_used_token_revokes_replacement(
        pg_test_data
):
    engine = pg_test_data["engine"]
    original_token = pg_test_data["token"]
    original_jti = pg_test_data["jti"]
    family_id = pg_test_data["family_id"]

    with Session(engine) as db:
        _, refresh_b = rotate_refresh_token(
            refresh_token= original_token,
            db=db
        )

        assert not db.in_transaction()

    payload_b = decode_refresh_token(refresh_b)

    with Session(engine) as db:
        logout_refresh_session(
            refresh_token= original_token,
            db=db
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


def test_postgres_logout_preserves_other_family(pg_test_data):
    engine = pg_test_data["engine"]
    user_id = pg_test_data["user_id"]
    original_token = pg_test_data["token"]
    original_jti = pg_test_data["jti"]

    other_family_id = str(uuid.uuid4())

    _, other_jti, other_expires_at = create_refresh_token(
        user_id=user_id,
        family_id=other_family_id,
    )

    with Session(engine) as db:
        other_record = RefreshToken(
            jti=other_jti,
            user_id=user_id,
            family_id=other_family_id,
            expires_at=other_expires_at,
            status=RefreshTokenStatus.ACTIVE,
        )

        db.add(other_record)
        db.commit()

    with Session(engine) as db:
        logout_refresh_session(
            refresh_token=original_token,
            db=db,
        )

        assert not db.in_transaction()

    with Session(engine) as db:
        original_record = (
            db.query(RefreshToken)
            .filter(RefreshToken.jti == original_jti)
            .one()
        )

        other_record = (
            db.query(RefreshToken)
            .filter(RefreshToken.jti == other_jti)
            .one()
        )

        assert original_record.status == RefreshTokenStatus.REVOKED
        assert original_record.revoked_at is not None

        assert other_record.status == RefreshTokenStatus.ACTIVE
        assert other_record.revoked_at is None
        assert other_record.used_at is None

        assert original_record.family_id != other_record.family_id
        assert original_record.user_id == other_record.user_id


def test_postgres_inactive_user_refresh_revokes_family(
    pg_test_data,
):
    engine = pg_test_data["engine"]
    user_id = pg_test_data["user_id"]
    original_token = pg_test_data["token"]
    original_jti = pg_test_data["jti"]
    family_id = pg_test_data["family_id"]

    with Session(engine) as db:
        user = (
            db.query(User)
            .filter(User.id == user_id)
            .one()
        )

        user.is_active = False
        db.commit()

    with Session(engine) as db:
        with pytest.raises(InactiveUserError):
            rotate_refresh_token(
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
            .filter(RefreshToken.family_id == family_id)
            .all()
        )

        assert len(family_records) == 1

        assert all(
            record.status != RefreshTokenStatus.ACTIVE
            for record in family_records
        )


def test_postgres_rotation_rolls_back_on_failure(
    pg_test_data,
    monkeypatch,
):
    engine = pg_test_data["engine"]
    original_token = pg_test_data["token"]
    original_jti = pg_test_data["jti"]
    family_id = pg_test_data["family_id"]

    def fail_create_refresh_token(user_id, family_id):
        raise RuntimeError(
            "Simulated PostgreSQL rotation failure"
        )

    monkeypatch.setattr(
        user_service,
        "create_refresh_token",
        fail_create_refresh_token,
    )

    with Session(engine) as db:
        with pytest.raises(
            RuntimeError,
            match="Simulated PostgreSQL rotation failure",
        ):
            rotate_refresh_token(
                refresh_token=original_token,
                db=db,
            )

        assert not db.in_transaction()

    with Session(engine) as db:
        original_record = (
            db.query(RefreshToken)
            .filter(RefreshToken.jti == original_jti)
            .one()
        )

        assert original_record.status == RefreshTokenStatus.ACTIVE
        assert original_record.used_at is None
        assert original_record.revoked_at is None

        family_records = (
            db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id)
            .all()
        )

        assert len(family_records) == 1

def test_postgres_logout_rolls_back_when_commit_fails(
    pg_test_data,
    monkeypatch,
):
    engine = pg_test_data["engine"]
    original_token = pg_test_data["token"]
    original_jti = pg_test_data["jti"]

    def fail_commit():
        raise RuntimeError(
            "Simulated PostgreSQL logout commit failure"
        )

    with Session(engine) as db:
        monkeypatch.setattr(
            db,
            "commit",
            fail_commit,
        )

        with pytest.raises(
            RuntimeError,
            match="Simulated PostgreSQL logout commit failure",
        ):
            user_service.logout_refresh_session(
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

        assert token_record.status == RefreshTokenStatus.ACTIVE
        assert token_record.revoked_at is None
        assert token_record.used_at is None

def test_postgres_reuse_rolls_back_when_commit_fails(
    pg_test_data,
    monkeypatch,
):
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

    def fail_commit():
        raise RuntimeError(
            "Simulated PostgreSQL reuse commit failure"
        )

    with Session(engine) as db:
        monkeypatch.setattr(
            db,
            "commit",
            fail_commit,
        )

        with pytest.raises(
            RuntimeError,
            match="Simulated PostgreSQL reuse commit failure",
        ):
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

        assert token_b.status == RefreshTokenStatus.ACTIVE
        assert token_b.used_at is None
        assert token_b.revoked_at is None

        family_records = (
            db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id)
            .all()
        )

        assert len(family_records) == 2


def test_postgres_inactive_user_revokes_all_active_family_tokens(
    pg_test_data,
):
    engine = pg_test_data["engine"]
    user_id = pg_test_data["user_id"]
    family_id = pg_test_data["family_id"]
    original_token = pg_test_data["token"]
    original_jti = pg_test_data["jti"]

    _, second_jti, second_expires_at = create_refresh_token(
        user_id=user_id,
        family_id=family_id,
    )

    with Session(engine) as db:
        second_record = RefreshToken(
            jti=second_jti,
            user_id=user_id,
            family_id=family_id,
            expires_at=second_expires_at,
            status=RefreshTokenStatus.ACTIVE,
        )

        db.add(second_record)

        user = (
            db.query(User)
            .filter(User.id == user_id)
            .one()
        )

        user.is_active = False
        db.commit()

    with Session(engine) as db:
        with pytest.raises(InactiveUserError):
            rotate_refresh_token(
                refresh_token=original_token,
                db=db,
            )

        assert not db.in_transaction()

    with Session(engine) as db:
        family_records = (
            db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id)
            .all()
        )

        assert len(family_records) == 2

        records_by_jti = {
            record.jti: record
            for record in family_records
        }

        assert original_jti in records_by_jti
        assert second_jti in records_by_jti

        for record in family_records:
            assert record.status == RefreshTokenStatus.REVOKED
            assert record.revoked_at is not None
            assert record.used_at is None

def test_postgres_concurrent_rotation_allows_only_one_success(
    pg_test_data,
):
    engine = pg_test_data["engine"]
    original_token = pg_test_data["token"]
    original_jti = pg_test_data["jti"]
    family_id = pg_test_data["family_id"]

    barrier = Barrier(2, timeout=10)

    def attempt_rotation():
        
        with Session(engine) as db:
            barrier.wait()

            try:
                tokens = rotate_refresh_token(
                    refresh_token=original_token,
                    db=db,
                )

            except RefreshTokenReuseDetectedError:
                assert not db.in_transaction()
                return "reuse", None

            else:
                assert not db.in_transaction()
                return "success", tokens

    
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(attempt_rotation)
        future_b = executor.submit(attempt_rotation)

        result_a = future_a.result(timeout=20)
        result_b = future_b.result(timeout=20)

    results = [result_a, result_b]

    outcomes = [result[0] for result in results]

    assert sorted(outcomes) == [
        "reuse",
        "success",
    ]

    successful_tokens = [
        tokens
        for outcome, tokens in results
        if outcome == "success"
    ]

    assert len(successful_tokens) == 1

    _, new_refresh_token = successful_tokens[0]

    new_payload = decode_refresh_token(new_refresh_token)

    assert new_payload["jti"] != original_jti
    assert new_payload["family_id"] == family_id

    with Session(engine) as db:
        family_records = (
            db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id)
            .all()
        )

        assert len(family_records) == 2

        records_by_jti = {
            record.jti: record
            for record in family_records
        }

        token_a = records_by_jti[original_jti]
        token_b = records_by_jti[new_payload["jti"]]

        assert token_a.status == RefreshTokenStatus.USED
        assert token_a.used_at is not None

        assert token_b.status == RefreshTokenStatus.REVOKED
        assert token_b.revoked_at is not None
        assert token_b.used_at is None

        assert all(
            record.status != RefreshTokenStatus.ACTIVE
            for record in family_records
        )


def test_postgres_concurrent_reuse_and_rotation(
    pg_test_data,
):
    engine = pg_test_data["engine"]
    token_a = pg_test_data["token"]
    jti_a = pg_test_data["jti"]
    family_id = pg_test_data["family_id"]

    # Step 1: Create Token B by rotating Token A
    with Session(engine) as db:
        _, token_b = rotate_refresh_token(
            refresh_token=token_a,
            db=db,
        )

        assert not db.in_transaction()

    payload_b = decode_refresh_token(token_b)
    jti_b = payload_b["jti"]

    barrier = Barrier(2, timeout=10)

    # Step 2: Reuse the old Token A
    def reuse_token_a():
        with Session(engine) as db:
            barrier.wait()

            with pytest.raises(
                RefreshTokenReuseDetectedError
            ):
                rotate_refresh_token(
                    refresh_token=token_a,
                    db=db,
                )

            assert not db.in_transaction()

        return "reuse"

    # Step 3: Rotate Token B concurrently
    def rotate_token_b():
        with Session(engine) as db:
            barrier.wait()

            try:
                tokens = rotate_refresh_token(
                    refresh_token=token_b,
                    db=db,
                )

            except InvalidTokenError:
                assert not db.in_transaction()
                return "rejected", None

            else:
                assert not db.in_transaction()
                return "success", tokens

    # Step 4: Execute both operations concurrently
    with ThreadPoolExecutor(max_workers=2) as executor:
        reuse_future = executor.submit(reuse_token_a)
        rotation_future = executor.submit(rotate_token_b)

        reuse_outcome = reuse_future.result(timeout=20)
        rotation_outcome, issued_tokens = (
            rotation_future.result(timeout=20)
        )

    assert reuse_outcome == "reuse"

    assert rotation_outcome in (
        "rejected",
        "success",
    )

    # Step 5: Verify the final committed state
    with Session(engine) as db:
        family_records = (
            db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id)
            .all()
        )

        records_by_jti = {
            record.jti: record
            for record in family_records
        }

        record_a = records_by_jti[jti_a]
        record_b = records_by_jti[jti_b]

        assert record_a.status == RefreshTokenStatus.USED
        assert record_a.used_at is not None

        assert all(
            record.status != RefreshTokenStatus.ACTIVE
            for record in family_records
        )

        if rotation_outcome == "rejected":
            assert issued_tokens is None
            assert len(family_records) == 2

            assert record_b.status == RefreshTokenStatus.REVOKED
            assert record_b.revoked_at is not None

        else:
            assert issued_tokens is not None
            assert len(family_records) == 3

            assert record_b.status == RefreshTokenStatus.USED
            assert record_b.used_at is not None

            _, token_c = issued_tokens
            payload_c = decode_refresh_token(token_c)

            assert payload_c["family_id"] == family_id
            assert payload_c["jti"] not in (jti_a, jti_b)

            record_c = records_by_jti[payload_c["jti"]]

            assert record_c.status == RefreshTokenStatus.REVOKED
            assert record_c.revoked_at is not None
            assert record_c.used_at is None

def test_postgres_concurrent_rotation_and_logout(
    pg_test_data,
):
    engine = pg_test_data["engine"]
    original_token = pg_test_data["token"]
    original_jti = pg_test_data["jti"]
    family_id = pg_test_data["family_id"]

    barrier = Barrier(2, timeout=10)

    def attempt_rotation():
        with Session(engine) as db:
            barrier.wait()

            try:
                tokens = rotate_refresh_token(
                    refresh_token=original_token,
                    db=db,
                )

            except InvalidTokenError:
                assert not db.in_transaction()
                return "rejected", None

            else:
                assert not db.in_transaction()
                return "success", tokens

    def attempt_logout():
        with Session(engine) as db:
            barrier.wait()

            logout_refresh_session(
                refresh_token=original_token,
                db=db,
            )

            assert not db.in_transaction()
            return "logout"

    with ThreadPoolExecutor(max_workers=2) as executor:
        rotation_future = executor.submit(attempt_rotation)
        logout_future = executor.submit(attempt_logout)

        rotation_outcome, issued_tokens = (
            rotation_future.result(timeout=20)
        )

        logout_outcome = logout_future.result(timeout=20)

    assert logout_outcome == "logout"
    assert rotation_outcome in ("success", "rejected")

    with Session(engine) as db:
        family_records = (
            db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id)
            .all()
        )

        records_by_jti = {
            record.jti: record
            for record in family_records
        }

        original_record = records_by_jti[original_jti]

        assert all(
            record.status != RefreshTokenStatus.ACTIVE
            for record in family_records
        )

        if rotation_outcome == "rejected":
            assert issued_tokens is None
            assert len(family_records) == 1

            assert original_record.status == RefreshTokenStatus.REVOKED
            assert original_record.revoked_at is not None
            assert original_record.used_at is None

        else:
            assert issued_tokens is not None
            assert len(family_records) == 2

            assert original_record.status == RefreshTokenStatus.USED
            assert original_record.used_at is not None

            _, new_refresh_token = issued_tokens
            new_payload = decode_refresh_token(new_refresh_token)

            new_record = records_by_jti[new_payload["jti"]]

            assert new_record.status == RefreshTokenStatus.REVOKED
            assert new_record.revoked_at is not None
            assert new_record.used_at is None
            assert new_record.family_id == family_id

def test_postgres_rotation_locks_before_logout(
    pg_test_data,
    monkeypatch,
):
    engine = pg_test_data["engine"]
    original_token = pg_test_data["token"]
    original_jti = pg_test_data["jti"]
    family_id = pg_test_data["family_id"]

    rotation_has_lock = Event()
    logout_started = Event()
    allow_rotation = Event()

    original_begin = (
        user_service.begin_protected_refresh_transaction
    )

    # Step 1: Pause rotation after acquiring the user lock.
    def controlled_begin(db, user_id):
        original_begin(
            db=db,
            user_id=user_id,
        )

        if not rotation_has_lock.is_set():
            rotation_has_lock.set()

            if not allow_rotation.wait(timeout=10):
                raise TimeoutError(
                    "Rotation was not released"
                )

    monkeypatch.setattr(
        user_service,
        "begin_protected_refresh_transaction",
        controlled_begin,
    )

    # Step 2: Rotation worker
    def run_rotation():
        with Session(engine) as db:
            tokens = rotate_refresh_token(
                refresh_token=original_token,
                db=db,
            )

            assert not db.in_transaction()
            return tokens

    # Step 3: Logout worker
    def run_logout():
        with Session(engine) as db:
            logout_started.set()

            logout_refresh_session(
                refresh_token=original_token,
                db=db,
            )

            assert not db.in_transaction()

    # Step 4: Control the execution order.
    with ThreadPoolExecutor(max_workers=2) as executor:
        rotation_future = executor.submit(run_rotation)

        try:
            assert rotation_has_lock.wait(timeout=10)

            logout_future = executor.submit(run_logout)

            assert logout_started.wait(timeout=10)

        finally:
            # Always release the paused worker.
            allow_rotation.set()

        issued_tokens = rotation_future.result(timeout=20)
        logout_future.result(timeout=20)

    # Step 5: Verify the committed database state.
    _, refresh_b = issued_tokens
    payload_b = decode_refresh_token(refresh_b)

    with Session(engine) as db:
        family_records = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.family_id == family_id
            )
            .all()
        )

        assert len(family_records) == 2

        records_by_jti = {
            record.jti: record
            for record in family_records
        }

        record_a = records_by_jti[original_jti]
        record_b = records_by_jti[payload_b["jti"]]

        assert record_a.status == RefreshTokenStatus.USED
        assert record_a.used_at is not None

        assert record_b.status == RefreshTokenStatus.REVOKED
        assert record_b.revoked_at is not None
        assert record_b.used_at is None

        assert all(
            record.status != RefreshTokenStatus.ACTIVE
            for record in family_records
        )

def test_postgres_logout_locks_before_rotation(
    pg_test_data,
    monkeypatch,
):
    engine = pg_test_data["engine"]
    original_token = pg_test_data["token"]
    original_jti = pg_test_data["jti"]
    family_id = pg_test_data["family_id"]

    logout_has_lock = Event()
    rotation_started = Event()
    allow_logout = Event()

    original_begin = (
        user_service.begin_protected_refresh_transaction
    )

    def controlled_begin(db, user_id):
        original_begin(
            db=db,
            user_id=user_id,
        )

        if not logout_has_lock.is_set():
            logout_has_lock.set()

            if not allow_logout.wait(timeout=10):
                raise TimeoutError(
                    "Logout was not released"
                )

    monkeypatch.setattr(
        user_service,
        "begin_protected_refresh_transaction",
        controlled_begin,
    )

    def run_logout():
        with Session(engine) as db:
            logout_refresh_session(
                refresh_token=original_token,
                db=db,
            )

            assert not db.in_transaction()
            return "logout"

    def run_rotation():
        with Session(engine) as db:
            rotation_started.set()

            try:
                tokens = rotate_refresh_token(
                    refresh_token=original_token,
                    db=db,
                )

            except InvalidTokenError:
                assert not db.in_transaction()
                return "rejected", None

            else:
                assert not db.in_transaction()
                return "success", tokens

    with ThreadPoolExecutor(max_workers=2) as executor:
        logout_future = executor.submit(run_logout)

        try:
            assert logout_has_lock.wait(timeout=10)

            rotation_future = executor.submit(run_rotation)

            assert rotation_started.wait(timeout=10)

        finally:
            allow_logout.set()

        logout_outcome = logout_future.result(timeout=20)

        rotation_outcome, issued_tokens = (
            rotation_future.result(timeout=20)
        )

    assert logout_outcome == "logout"
    assert rotation_outcome == "rejected"
    assert issued_tokens is None

    with Session(engine) as db:
        family_records = (
            db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id)
            .all()
        )

        assert len(family_records) == 1

        original_record = family_records[0]

        assert original_record.jti == original_jti

        assert (
            original_record.status
            == RefreshTokenStatus.REVOKED
        )

        assert original_record.revoked_at is not None
        assert original_record.used_at is None

        assert all(
            record.status != RefreshTokenStatus.ACTIVE
            for record in family_records
        )

def test_postgres_reuse_locks_before_rotation(
    pg_test_data,
    monkeypatch,
):
    engine = pg_test_data["engine"]
    token_a = pg_test_data["token"]
    jti_a = pg_test_data["jti"]
    family_id = pg_test_data["family_id"]

    with Session(engine) as db:
        _, token_b = rotate_refresh_token(
            refresh_token=token_a,
            db=db,
        )
        assert not db.in_transaction()

    payload_b = decode_refresh_token(token_b)
    jti_b = payload_b["jti"]

    reuse_has_lock = Event()
    rotation_started = Event()
    allow_reuse = Event()

    original_begin = (
        user_service.begin_protected_refresh_transaction
    )

    def controlled_begin(db, user_id):
        original_begin(
            db=db,
            user_id=user_id,
        )

        if not reuse_has_lock.is_set():
            reuse_has_lock.set()

            if not allow_reuse.wait(timeout=10):
                raise TimeoutError(
                    "Reuse was not released"
                )

    monkeypatch.setattr(
        user_service,
        "begin_protected_refresh_transaction",
        controlled_begin,
    )

    def run_reuse():
        with Session(engine) as db:
            with pytest.raises(
                RefreshTokenReuseDetectedError
            ):
                rotate_refresh_token(
                    refresh_token=token_a,
                    db=db,
                )

            assert not db.in_transaction()
            return "reuse"
        
    def run_rotation():
        with Session(engine) as db:
            rotation_started.set()

            try:
                tokens = rotate_refresh_token(
                    refresh_token=token_b,
                    db=db,
                )

            except InvalidTokenError:
                assert not db.in_transaction()
                return "rejected", None

            else:
                assert not db.in_transaction()
                return "success", tokens


    with ThreadPoolExecutor(max_workers=2) as executor:
        reuse_future = executor.submit(run_reuse)

        try:
            assert reuse_has_lock.wait(timeout=10)

            rotation_future = executor.submit(
                run_rotation
            )

            assert rotation_started.wait(timeout=10)

        finally:
            allow_reuse.set()

        reuse_outcome = reuse_future.result(timeout=20)

        rotation_outcome, issued_tokens = (
            rotation_future.result(timeout=20)
        )

    assert reuse_outcome == "reuse"
    assert rotation_outcome == "rejected"
    assert issued_tokens is None

    with Session(engine) as db:
        family_records = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.family_id == family_id
            )
            .all()
        )

        assert len(family_records) == 2

        records_by_jti = {
            record.jti: record
            for record in family_records
        }

        record_a = records_by_jti[jti_a]
        record_b = records_by_jti[jti_b]

        assert record_a.status == RefreshTokenStatus.USED
        assert record_a.used_at is not None
        assert record_a.revoked_at is None

        assert record_b.status == RefreshTokenStatus.REVOKED
        assert record_b.revoked_at is not None
        assert record_b.used_at is None

        assert all(
            record.status != RefreshTokenStatus.ACTIVE
            for record in family_records
        )

def test_postgres_rotation_locks_before_reuse(
    pg_test_data,
    monkeypatch,
):
    engine = pg_test_data["engine"]
    token_a = pg_test_data["token"]
    jti_a = pg_test_data["jti"]
    family_id = pg_test_data["family_id"]

    # Step 1: Rotate A to create active Token B.
    with Session(engine) as db:
        _, token_b = rotate_refresh_token(
            refresh_token=token_a,
            db=db,
        )

        assert not db.in_transaction()

    payload_b = decode_refresh_token(token_b)
    jti_b = payload_b["jti"]

    rotation_has_lock = Event()
    reuse_started = Event()
    allow_rotation = Event()

    original_begin = (
        user_service.begin_protected_refresh_transaction
    )

    # Step 2: Pause Rotation B after acquiring the lock.
    def controlled_begin(db, user_id):
        original_begin(
            db=db,
            user_id=user_id,
        )

        if not rotation_has_lock.is_set():
            rotation_has_lock.set()

            if not allow_rotation.wait(timeout=10):
                raise TimeoutError(
                    "Rotation was not released"
                )

    monkeypatch.setattr(
        user_service,
        "begin_protected_refresh_transaction",
        controlled_begin,
    )

    # Step 3: Rotation B worker.
    def run_rotation():
        with Session(engine) as db:
            tokens = rotate_refresh_token(
                refresh_token=token_b,
                db=db,
            )

            assert not db.in_transaction()
            return tokens

    # Step 4: Reuse A worker.
    def run_reuse():
        with Session(engine) as db:
            reuse_started.set()

            with pytest.raises(
                RefreshTokenReuseDetectedError
            ):
                rotate_refresh_token(
                    refresh_token=token_a,
                    db=db,
                )

            assert not db.in_transaction()
            return "reuse"

    # Step 5: Control execution order.
    with ThreadPoolExecutor(max_workers=2) as executor:
        rotation_future = executor.submit(
            run_rotation
        )

        try:
            assert rotation_has_lock.wait(timeout=10)

            reuse_future = executor.submit(
                run_reuse
            )

            assert reuse_started.wait(timeout=10)

        finally:
            # Always release the paused Rotation.
            allow_rotation.set()

        issued_tokens = rotation_future.result(
            timeout=20
        )

        reuse_outcome = reuse_future.result(
            timeout=20
        )

    assert reuse_outcome == "reuse"

    # Step 6: Identify newly issued Token C.
    _, token_c = issued_tokens

    payload_c = decode_refresh_token(token_c)
    jti_c = payload_c["jti"]

    assert payload_c["family_id"] == family_id
    assert jti_c not in (jti_a, jti_b)

    # Step 7: Verify final committed state.
    with Session(engine) as db:
        family_records = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.family_id == family_id
            )
            .all()
        )

        assert len(family_records) == 3

        records_by_jti = {
            record.jti: record
            for record in family_records
        }

        record_a = records_by_jti[jti_a]
        record_b = records_by_jti[jti_b]
        record_c = records_by_jti[jti_c]

        assert record_a.status == RefreshTokenStatus.USED
        assert record_a.used_at is not None
        assert record_a.revoked_at is None

        assert record_b.status == RefreshTokenStatus.USED
        assert record_b.used_at is not None
        assert record_b.revoked_at is None

        assert record_c.status == RefreshTokenStatus.REVOKED
        assert record_c.revoked_at is not None
        assert record_c.used_at is None

        assert all(
            record.status != RefreshTokenStatus.ACTIVE
            for record in family_records
        )
