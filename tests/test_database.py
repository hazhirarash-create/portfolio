import uuid
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from models.models import RefreshToken, RefreshTokenStatus

def test_sqlite_foreign_keys_are_enabled(db_session):
    result = db_session.execute(
        text("PRAGMA foreign_keys;")
    ).scalar_one()

    assert result == 1

def test_refresh_token_with_missing_user_is_rejected(
        db_session
        ):
    token_record = RefreshToken(
        jti = str(uuid.uuid4()),
        user_id = 999999,
        family_id = str(uuid.uuid4()),
        expires_at = datetime.now(timezone.utc) + timedelta(days=7),
        status = RefreshTokenStatus.ACTIVE
    )

    db_session.add(token_record)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()