from models.models import RefreshToken, RefreshTokenStatus
from services import user_service
from services.user_service import rotate_refresh_token
from sqlalchemy.orm import Session
import pytest
from conftest import active_refresh_token
from security.jwt_handler import (decode_refresh_token,
                                  create_refresh_token)
import uuid

def test_logout_revokes_active_refresh_token(active_refresh_token,
                                             db_session
                                             ):
    original_jti = active_refresh_token["jti"]

    user_service.logout_refresh_session(
        refresh_token= active_refresh_token["token"],
        db= db_session
    )

    assert not db_session.in_transaction()

    with Session(bind=db_session.get_bind()) as verification_db:
        token_record = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == original_jti)
            .one()
        )

        assert token_record.status == RefreshTokenStatus.REVOKED
        assert token_record.revoked_at is not None
        assert token_record.used_at is None

def test_logout_with_used_token_revokes_active_replacement(
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

    user_service.logout_refresh_session(
        refresh_token=original_token,
        db=db_session,
    )

    assert not db_session.in_transaction()

    with Session(bind=db_session.get_bind()) as verification_db:
        token_a = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == original_jti)
            .one()
        )

        token_b = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == payload_b["jti"])
            .one()
        )

        assert token_a.status == RefreshTokenStatus.USED
        assert token_a.used_at is not None
        assert token_a.revoked_at is None

        assert token_b.status == RefreshTokenStatus.REVOKED
        assert token_b.revoked_at is not None
        assert token_b.used_at is None

        family_token_count = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id)
            .count()
        )

        assert family_token_count == 2

def test_logout_is_idempotent_for_revoked_token(
    db_session,
    active_refresh_token,
):
    original_token = active_refresh_token["token"]
    original_jti = active_refresh_token["jti"]

    user_service.logout_refresh_session(
        refresh_token=original_token,
        db=db_session,
    )

    with Session(bind=db_session.get_bind()) as verification_db:
        token_record = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == original_jti)
            .one()
        )

        first_revoked_at = token_record.revoked_at

        assert token_record.status == RefreshTokenStatus.REVOKED
        assert first_revoked_at is not None

    user_service.logout_refresh_session(
        refresh_token=original_token,
        db=db_session,
    )

    assert not db_session.in_transaction()

    with Session(bind=db_session.get_bind()) as verification_db:
        token_record = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == original_jti)
            .one()
        )

        assert token_record.status == RefreshTokenStatus.REVOKED
        assert token_record.revoked_at == first_revoked_at
        assert token_record.used_at is None

def test_logout_does_not_revoke_another_family(
    db_session,
    test_user,
    active_refresh_token,
):
    target_token = active_refresh_token["token"]
    target_jti = active_refresh_token["jti"]
    target_family_id = active_refresh_token["family_id"]

    other_family_id = str(uuid.uuid4())

    (
        _,
        other_jti,
        other_expires_at,
    ) = create_refresh_token(
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

    user_service.logout_refresh_session(
        refresh_token=target_token,
        db=db_session,
    )

    assert not db_session.in_transaction()

    with Session(bind=db_session.get_bind()) as verification_db:
        target_record = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == target_jti)
            .one()
        )

        unaffected_record = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == other_jti)
            .one()
        )

        assert target_record.user_id == unaffected_record.user_id
        assert target_record.family_id == target_family_id
        assert unaffected_record.family_id == other_family_id

        assert target_record.status == RefreshTokenStatus.REVOKED
        assert target_record.revoked_at is not None

        assert unaffected_record.status == RefreshTokenStatus.ACTIVE
        assert unaffected_record.used_at is None
        assert unaffected_record.revoked_at is None

def test_logout_rolls_back_when_commit_fails(active_refresh_token,
                                             monkeypatch,
                                             db_session):
    original_jti = active_refresh_token["jti"]

    def fail_commit():
        raise RuntimeError("simulate logout commit failure")

    monkeypatch.setattr(
        db_session,
        "commit",
        fail_commit
    )

    with pytest.raises(
        RuntimeError,
        match= "simulate logout commit failure"
    ):
        user_service.logout_refresh_session(
            refresh_token= active_refresh_token["token"],
            db= db_session
            )

    assert not db_session.in_transaction()

    with Session(bind=db_session.get_bind()) as verification_db:
        token_record = (verification_db.query(RefreshToken)
                        .filter(RefreshToken.jti == original_jti)
                        .one()
                        )

        assert token_record.status == RefreshTokenStatus.ACTIVE
        assert token_record.revoked_at is None
        assert token_record.used_at is None

def test_logout_rejects_existing_transaction_without_ending_it(
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
            user_service.logout_refresh_session(
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