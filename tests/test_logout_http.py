from sqlalchemy.orm import Session
from models.models import RefreshToken, RefreshTokenStatus


def test_logout_http_revokes_session(
        http_client,
        db_session,
        active_refresh_token):

    response = http_client.post(
        "/users/logout",
        json={"refresh_token": active_refresh_token["token"]},
    )

    assert response.status_code == 204
    assert response.content == b""

    with Session(bind=db_session.get_bind()) as verification_db:
        token_record = (
            verification_db.query(RefreshToken)
            .filter(RefreshToken.jti == active_refresh_token["jti"])
            .one()
        )

        assert token_record.status == RefreshTokenStatus.REVOKED
        assert token_record.revoked_at is not None
        assert token_record.used_at is None