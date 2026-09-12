from sqlalchemy import inspect
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
from datetime import datetime, timezone
from sqlalchemy import update

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

def test_failed_claim_rejects_token_revoked_before_update(
    db_session,
    active_refresh_token,
    monkeypatch,
):
    original_jti = active_refresh_token["jti"]
    family_id = active_refresh_token["family_id"]

    real_execute = db_session.execute
    claim_rowcounts = []
    state_change_simulated = False

    def execute_with_revocation(statement, *args, **kwargs):
        nonlocal state_change_simulated

        if (
            getattr(statement, "is_update", False)
            and not state_change_simulated
        ):
            state_change_simulated = True

            real_execute(
                update(RefreshToken)
                .where(RefreshToken.jti == original_jti)
                .values(
                    status=RefreshTokenStatus.REVOKED,
                    revoked_at=datetime.now(timezone.utc),
                )
            )
            db_session.commit()

            result = real_execute(statement, *args, **kwargs)
            claim_rowcounts.append(result.rowcount)

            return result

        return real_execute(statement, *args, **kwargs)

    def unexpected_family_revocation(*args, **kwargs):
        pytest.fail("REVOKED token must not trigger family revocation")

    monkeypatch.setattr(
        db_session,
        "execute",
        execute_with_revocation,
    )

    monkeypatch.setattr(
        user_service,
        "revoke_token_family",
        unexpected_family_revocation,
    )

    with pytest.raises(InvalidTokenError):
        user_service.rotate_refresh_token(
            refresh_token=active_refresh_token["token"],
            db=db_session,
        )

    assert state_change_simulated
    assert claim_rowcounts == [0]

    with Session(bind=db_session.get_bind()) as verification_db:
        record = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == original_jti)
            .one()
        )

        assert record.status == RefreshTokenStatus.REVOKED
        assert record.revoked_at is not None
        assert record.used_at is None

        family_token_count = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id)
            .count()
        )

        assert family_token_count == 1


def test_failed_claim_detects_used_token_and_revokes_family(
    db_session,
    test_user,
    active_refresh_token,
    monkeypatch,
):
    original_jti = active_refresh_token["jti"]
    family_id = active_refresh_token["family_id"]

    real_execute = db_session.execute

    claim_rowcounts = []
    state_change_simulated = False
    created_token_jtis = []

    def execute_with_completed_rotation(
        statement,
        *args,
        **kwargs,
    ):
        nonlocal state_change_simulated

        if (
            getattr(statement, "is_update", False)
            and not state_change_simulated
        ):
            state_change_simulated = True

            _, new_jti, new_expires_at = (
                user_service.create_refresh_token(
                    user_id=test_user.id,
                    family_id=family_id,
                )
            )

            real_execute(
                update(RefreshToken)
                .where(RefreshToken.jti == original_jti)
                .values(
                    status=RefreshTokenStatus.USED,
                    used_at=datetime.now(timezone.utc),
                )
            )

            replacement_record = RefreshToken(
                jti=new_jti,
                user_id=test_user.id,
                family_id=family_id,
                expires_at=new_expires_at,
                status=RefreshTokenStatus.ACTIVE,
            )

            db_session.add(replacement_record)
            db_session.commit()

            created_token_jtis.append(new_jti)

            result = real_execute(statement, *args, **kwargs)
            claim_rowcounts.append(result.rowcount)

            return result

        return real_execute(statement, *args, **kwargs)

    monkeypatch.setattr(
        db_session,
        "execute",
        execute_with_completed_rotation,
    )

    with pytest.raises(RefreshTokenReuseDetectedError):
        user_service.rotate_refresh_token(
            refresh_token=active_refresh_token["token"],
            db=db_session,
        )

    assert state_change_simulated
    assert claim_rowcounts == [0]
    assert len(created_token_jtis) == 1
    assert not db_session.in_transaction()

    replacement_jti = created_token_jtis[0]

    with Session(bind=db_session.get_bind()) as verification_db:
        token_a = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == original_jti)
            .one()
        )

        token_b = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == replacement_jti)
            .one()
        )

        assert token_a.status == RefreshTokenStatus.USED
        assert token_a.used_at is not None
        assert token_a.revoked_at is None

        assert token_b.status == RefreshTokenStatus.REVOKED
        assert token_b.revoked_at is not None
        assert token_b.used_at is None

        assert token_b.family_id == family_id
        assert token_b.user_id == token_a.user_id

        family_token_count = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id)
            .count()
        )

        assert family_token_count == 2