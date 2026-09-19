import pytest

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database import get_db
from main import app
from models.models import RefreshToken, RefreshTokenStatus
from security.jwt_handler import decode_refresh_token


@pytest.fixture
def http_client(db_session, monkeypatch):

    test_engine = db_session.get_bind()

    def override_get_db():

        with Session(bind=test_engine) as request_db:
            yield request_db

    monkeypatch.setitem(
        app.dependency_overrides,
        get_db,
        override_get_db,
    )

    with TestClient(app) as client:
        yield client


def test_refresh_reuse_response_and_revocation(
    http_client,
    db_session,
    active_refresh_token,
):
    token_a = active_refresh_token["token"]
    jti_a = active_refresh_token["jti"]
    family_id = active_refresh_token["family_id"]

    first_response = http_client.post(
        "/users/refresh",
        json={"refresh_token": token_a},
    )

    assert first_response.status_code == 200

    token_pair = first_response.json()

    assert token_pair["token_type"] == "bearer"
    assert isinstance(token_pair["access_token"], str)
    assert token_pair["access_token"]
    assert isinstance(token_pair["refresh_token"], str)
    assert token_pair["refresh_token"]

    token_b = token_pair["refresh_token"]
    payload_b = decode_refresh_token(token_b)

    assert payload_b["jti"] != jti_a
    assert payload_b["family_id"] == family_id

    reuse_response = http_client.post(
        "/users/refresh",
        json={"refresh_token": token_a},
    )

    assert reuse_response.status_code == 401
    assert reuse_response.json() == {
        "detail": "Refresh token reuse detected",
    }
    assert reuse_response.headers["www-authenticate"] == "Bearer"

    with Session(bind=db_session.get_bind()) as verification_db:
        record_a = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == jti_a)
            .one()
        )

        record_b = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == payload_b["jti"])
            .one()
        )

        assert record_a.status == RefreshTokenStatus.USED
        assert record_a.used_at is not None
        assert record_a.revoked_at is None

        assert record_b.status == RefreshTokenStatus.REVOKED
        assert record_b.revoked_at is not None
        assert record_b.used_at is None


    revoked_response = http_client.post(
        "/users/refresh",
        json={"refresh_token": token_b},
    )

    assert revoked_response.status_code == 401
    assert revoked_response.json() == {
        "detail": "Could not validate credentials",
    }
    assert revoked_response.headers["www-authenticate"] == "Bearer"

    
    with Session(bind=db_session.get_bind()) as verification_db:
        family_records = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.family_id == family_id)
            .all()
        )

        assert len(family_records) == 2

        for record in family_records:
            assert record.status != RefreshTokenStatus.ACTIVE
