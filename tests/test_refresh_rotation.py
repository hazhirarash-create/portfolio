from models.models import User, RefreshToken, RefreshTokenStatus
import pytest
from sqlalchemy import select
from services import user_service
from sqlalchemy.orm import Session
from security.jwt_handler import decode_refresh_token
from exceptions.auth_exceptions import (
    InvalidTokenError,
    RefreshTokenReuseDetectedError,
)
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from tests.conftest import active_refresh_token, db_session, test_user

def test_rotation_rolls_back_when_token_creation_fails(
    db_session,
    active_refresh_token,
    monkeypatch,
):
    original_jti = active_refresh_token["jti"]
    family_id = active_refresh_token["family_id"]

    def fail_create_refresh_token(user_id, family_id):
        status_before_failure = db_session.execute(
            select(RefreshToken.status).where(
                RefreshToken.jti == original_jti,
            )
        ).scalar_one()

        assert status_before_failure == RefreshTokenStatus.USED

        raise RuntimeError("Simulated refresh creation failure")

    monkeypatch.setattr(
        user_service,
        "create_refresh_token",
        fail_create_refresh_token,
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated refresh creation failure",
    ):
        user_service.rotate_refresh_token(
            refresh_token=active_refresh_token["token"],
            db=db_session,
        )

    assert not db_session.in_transaction()

    token_record = (
        db_session.query(RefreshToken)
        .filter(RefreshToken.jti == original_jti)
        .populate_existing()
        .one()
    )

    assert token_record.status == RefreshTokenStatus.ACTIVE
    assert token_record.used_at is None

    family_token_count = (
        db_session.query(RefreshToken)
        .filter(RefreshToken.family_id == family_id)
        .count()
    )

    assert family_token_count == 1

def test_rotation_succeeds(
    db_session,
    active_refresh_token,
):
    original_jti = active_refresh_token["jti"]
    original_family_id = active_refresh_token["family_id"]

    new_access_token, new_refresh_token = (
        user_service.rotate_refresh_token(
            refresh_token=active_refresh_token["token"],
            db=db_session,
        )
    )

    assert isinstance(new_access_token, str)
    assert new_access_token

    assert isinstance(new_refresh_token, str)
    assert new_refresh_token

    new_payload = decode_refresh_token(new_refresh_token)

    assert new_payload["jti"] != original_jti
    assert new_payload["family_id"] == original_family_id

    assert not db_session.in_transaction()

    with Session(bind=db_session.get_bind()) as verification_db:
        old_record = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == original_jti)
            .one()
        )

        new_record = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == new_payload["jti"])
            .one()
        )

        assert old_record.status == RefreshTokenStatus.USED
        assert old_record.used_at is not None
        assert old_record.revoked_at is None

        assert new_record.status == RefreshTokenStatus.ACTIVE
        assert new_record.used_at is None
        assert new_record.revoked_at is None

        assert new_record.family_id == original_family_id
        assert new_record.user_id == old_record.user_id
        assert new_payload["user_id"] == new_record.user_id

        family_token_count = (
            verification_db.query(RefreshToken)
            .filter(
                RefreshToken.family_id == original_family_id,
            )
            .count()
        )

        assert family_token_count == 2

def test_reuse_revokes_active_tokens_in_family(
    db_session,
    active_refresh_token,
):
    original_token = active_refresh_token["token"]
    original_jti = active_refresh_token["jti"]
    family_id = active_refresh_token["family_id"]

    _, refresh_b = user_service.rotate_refresh_token(
        refresh_token=original_token,
        db=db_session,
    )

    payload_b = decode_refresh_token(refresh_b)

    with Session(bind=db_session.get_bind()) as verification_db:
        original_record = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == original_jti)
            .one()
        )

        original_used_at = original_record.used_at

        assert original_record.status == RefreshTokenStatus.USED
        assert original_used_at is not None

    with pytest.raises(RefreshTokenReuseDetectedError):
        user_service.rotate_refresh_token(
            refresh_token=original_token,
            db=db_session,
        )

    assert not db_session.in_transaction()

    with Session(bind=db_session.get_bind()) as verification_db:
        old_record = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == original_jti)
            .one()
        )

        new_record = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == payload_b["jti"])
            .one()
        )

        assert old_record.status == RefreshTokenStatus.USED
        assert old_record.used_at == original_used_at
        assert old_record.revoked_at is None

        assert new_record.status == RefreshTokenStatus.REVOKED
        assert new_record.revoked_at is not None
        assert new_record.used_at is None

        family_token_count = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id)
            .count()
        )

        assert family_token_count == 2


def test_reuse_does_not_revoke_another_family(
    db_session,
    test_user,
    active_refresh_token,
):
    original_token = active_refresh_token["token"]
    target_family_id = active_refresh_token["family_id"]

    other_family_id = str(uuid.uuid4())

    (
        other_token,
        other_jti,
        other_expires_at,
    ) = user_service.create_refresh_token(
        user_id=test_user.id,
        family_id=other_family_id,
    )

    other_record = RefreshToken(
        jti=other_jti,
        user_id=test_user.id,
        family_id=other_family_id,
        expires_at=other_expires_at,
        status=RefreshTokenStatus.ACTIVE,
    )

    db_session.add(other_record)
    db_session.commit()

    assert other_family_id != target_family_id

    _, refresh_b = user_service.rotate_refresh_token(
        refresh_token=original_token,
        db=db_session,
    )

    payload_b = decode_refresh_token(refresh_b)

    with pytest.raises(RefreshTokenReuseDetectedError):
        user_service.rotate_refresh_token(
            refresh_token=original_token,
            db=db_session,
        )

    with Session(bind=db_session.get_bind()) as verification_db:
        revoked_record = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == payload_b["jti"])
            .one()
        )

        unaffected_record = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == other_jti)
            .one()
        )

        assert revoked_record.user_id == unaffected_record.user_id
        assert revoked_record.family_id == target_family_id
        assert unaffected_record.family_id == other_family_id

        assert revoked_record.status == RefreshTokenStatus.REVOKED
        assert revoked_record.revoked_at is not None

        assert unaffected_record.status == RefreshTokenStatus.ACTIVE
        assert unaffected_record.used_at is None
        assert unaffected_record.revoked_at is None

def test_reuse_rolls_back_when_security_commit_fails(
    db_session,
    active_refresh_token,
    monkeypatch,
):
    original_token = active_refresh_token["token"]
    original_jti = active_refresh_token["jti"]
    family_id = active_refresh_token["family_id"]

    _, refresh_b = user_service.rotate_refresh_token(
        refresh_token=original_token,
        db=db_session,
    )

    payload_b = decode_refresh_token(refresh_b)

    def fail_commit():
        raise RuntimeError("Simulated security commit failure")

    monkeypatch.setattr(
        db_session,
        "commit",
        fail_commit,
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated security commit failure",
    ):
        user_service.rotate_refresh_token(
            refresh_token=original_token,
            db=db_session,
        )

    assert not db_session.in_transaction()

    token_b = (
        db_session.query(RefreshToken)
        .filter(RefreshToken.jti == payload_b["jti"])
        .one()
    )

    assert token_b.status == RefreshTokenStatus.ACTIVE
    assert token_b.revoked_at is None

    with Session(bind=db_session.get_bind()) as verification_db:
        token_a = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == original_jti)
            .one()
        )

        persisted_b = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == payload_b["jti"])
            .one()
        )

        assert token_a.status == RefreshTokenStatus.USED
        assert token_a.used_at is not None
        assert token_a.revoked_at is None

        assert persisted_b.status == RefreshTokenStatus.ACTIVE
        assert persisted_b.used_at is None
        assert persisted_b.revoked_at is None

        family_token_count = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id)
            .count()
        )

        assert family_token_count == 2

def test_rotation_rejects_existing_transaction_without_ending_it(
    db_session,
    active_refresh_token,
):
    original_jti = active_refresh_token["jti"]

    token_record = (
        db_session.query(RefreshToken)
        .filter(RefreshToken.jti == original_jti)
        .one()
    )

    assert token_record.status == RefreshTokenStatus.ACTIVE

    caller_transaction = db_session.get_transaction()
    assert caller_transaction is not None

    try:
        token_record.status = RefreshTokenStatus.REVOKED
        db_session.flush()

        with pytest.raises(
            RuntimeError,
            match="without an active transaction",
        ):
            user_service.rotate_refresh_token(
                refresh_token=active_refresh_token["token"],
                db=db_session,
            )

        assert db_session.in_transaction()
        assert db_session.get_transaction() is caller_transaction

        db_session.refresh(token_record)

        assert token_record.status == RefreshTokenStatus.REVOKED

    finally:
        db_session.rollback()

    with Session(bind=db_session.get_bind()) as verification_db:
        persisted_record = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == original_jti)
            .one()
        )

        assert persisted_record.status == RefreshTokenStatus.ACTIVE


def test_concurrent_reuse_and_rotation_leave_no_active_tokens(
    db_session,
    active_refresh_token,
    monkeypatch,
):
    test_engine = db_session.get_bind()

    token_a = active_refresh_token["token"]
    jti_a = active_refresh_token["jti"]
    family_id = active_refresh_token["family_id"]

    _, token_b = user_service.rotate_refresh_token(
        refresh_token=token_a,
        db=db_session,
    )

    payload_b = decode_refresh_token(token_b)
    jti_b = payload_b["jti"]

    barrier = Barrier(2, timeout=5)

    real_begin_write_transaction = (
        user_service.begin_sqlite_write_transaction
    )

    def begin_write_transaction_with_barrier(db):
        assert not db.in_transaction()
        barrier.wait()
        real_begin_write_transaction(db=db)

    monkeypatch.setattr(
        user_service,
        "begin_sqlite_write_transaction",
        begin_write_transaction_with_barrier,
    )

    def reuse_token_a():
        with Session(bind=test_engine) as worker_db:
            with pytest.raises(RefreshTokenReuseDetectedError):
                user_service.rotate_refresh_token(
                    refresh_token=token_a,
                    db=worker_db,
                )

            assert not worker_db.in_transaction()

    def rotate_token_b():
        with Session(bind=test_engine) as worker_db:
            try:
                tokens = user_service.rotate_refresh_token(
                    refresh_token=token_b,
                    db=worker_db,
                )

            except InvalidTokenError:
                assert not worker_db.in_transaction()
                return "rejected", None

            else:
                assert not worker_db.in_transaction()
                return "success", tokens

    with ThreadPoolExecutor(max_workers=2) as executor:
        reuse_future = executor.submit(reuse_token_a)
        rotation_future = executor.submit(rotate_token_b)

        reuse_future.result(timeout=15)
        rotation_outcome, issued_tokens = (
            rotation_future.result(timeout=15)
        )

    with Session(bind=test_engine) as verification_db:
        family_records = (
            verification_db.query(RefreshToken)
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
        assert record_a.revoked_at is None

        for record in family_records:
            assert record.status != RefreshTokenStatus.ACTIVE

        if rotation_outcome == "rejected":
            assert issued_tokens is None
            assert len(family_records) == 2

            assert record_b.status == RefreshTokenStatus.REVOKED
            assert record_b.revoked_at is not None
            assert record_b.used_at is None

        else:
            assert rotation_outcome == "success"
            assert issued_tokens is not None
            assert len(family_records) == 3

            assert record_b.status == RefreshTokenStatus.USED
            assert record_b.used_at is not None
            assert record_b.revoked_at is None

            _, token_c = issued_tokens
            payload_c = decode_refresh_token(token_c)

            assert payload_c["family_id"] == family_id
            assert payload_c["jti"] not in (jti_a, jti_b)

            record_c = records_by_jti[payload_c["jti"]]

            assert record_c.status == RefreshTokenStatus.REVOKED
            assert record_c.revoked_at is not None
            assert record_c.used_at is None

            assert record_c.user_id == record_b.user_id
            assert payload_c["user_id"] == record_c.user_id


def test_concurrent_rotation_allows_only_one_success(
    db_session,
    active_refresh_token,
    monkeypatch,
):
    test_engine = db_session.get_bind()

    original_token = active_refresh_token["token"]
    original_jti = active_refresh_token["jti"]
    family_id = active_refresh_token["family_id"]

    barrier = Barrier(2, timeout=5)

    real_begin_write_transaction = (
        user_service.begin_sqlite_write_transaction
    )

    def begin_write_transaction_with_barrier(db):
        assert not db.in_transaction()

        barrier.wait()

        real_begin_write_transaction(db=db)

    monkeypatch.setattr(
        user_service,
        "begin_sqlite_write_transaction",
        begin_write_transaction_with_barrier,
    )

    def attempt_rotation():
        with Session(bind=test_engine) as worker_db:
            try:
                tokens = user_service.rotate_refresh_token(
                    refresh_token=original_token,
                    db=worker_db,
                )

            except RefreshTokenReuseDetectedError:
                assert not worker_db.in_transaction()
                return "reuse", None

            else:
                assert not worker_db.in_transaction()
                return "success", tokens

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(attempt_rotation)
        second_future = executor.submit(attempt_rotation)

        first_result = first_future.result(timeout=15)
        second_result = second_future.result(timeout=15)

    results = [first_result, second_result]

    outcomes = [result[0] for result in results]
    assert sorted(outcomes) == ["reuse", "success"]

    successful_tokens = [
        tokens
        for outcome, tokens in results
        if outcome == "success"
    ]

    assert len(successful_tokens) == 1

    _, issued_refresh_token = successful_tokens[0]
    issued_payload = decode_refresh_token(issued_refresh_token)

    assert issued_payload["jti"] != original_jti
    assert issued_payload["family_id"] == family_id

    with Session(bind=test_engine) as verification_db:
        family_records = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id)
            .all()
        )

        assert len(family_records) == 2

        records_by_jti = {
            record.jti: record
            for record in family_records
        }

        token_a = records_by_jti[original_jti]
        token_b = records_by_jti[issued_payload["jti"]]

        assert token_a.status == RefreshTokenStatus.USED
        assert token_a.used_at is not None
        assert token_a.revoked_at is None

        assert token_b.status == RefreshTokenStatus.REVOKED
        assert token_b.revoked_at is not None
        assert token_b.used_at is None

        assert token_b.user_id == token_a.user_id
        assert issued_payload["user_id"] == token_b.user_id