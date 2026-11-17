
from models.models import User, RefreshToken
import pytest
from main import app
from security.rate_limit import check_rate_limit


def test_register_user_success(
    db_session,
    http_client,
):

    registration_data = {
        "username": "new_portfolio_user",
        "email": "new_portfolio_user@example.com",
        "password": "UniquePortfolioPass_2026!Q7",
    }

    response = http_client.post(
        "/users",
        json=registration_data,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["username"] == (
        registration_data["username"]
    )
    assert data["email"] == registration_data["email"]

    assert data["is_active"] is True
    assert data["is_admin"] is False

    assert "password" not in data
    assert "hashed_password" not in data

    db_session.expire_all()

    saved_user = (
        db_session.query(User)
        .filter(
            User.username == registration_data["username"]
        )
        .one()
    )

    assert saved_user.email == registration_data["email"]

    assert saved_user.hashed_password != (
        registration_data["password"]
    )

    assert saved_user.hashed_password


@pytest.mark.parametrize(
    "duplicate_field",
    [
        "username",
        "email",
    ],
)
def test_register_user_rejects_duplicate_credentials(
    db_session,
    http_client,
    duplicate_field,
):
    first_user_data = {
        "username": "existing_user",
        "email": "existing@example.com",
        "password": "UniquePassword_2026!Q7",
    }

    first_response = http_client.post(
        "/users",
        json=first_user_data,
    )

    assert first_response.status_code == 201, (
        first_response.text
    )

    second_user_data = {
        "username": "another_user",
        "email": "another@example.com",
        "password": "AnotherStrongPassword_2026!Q7",
    }

    second_user_data[duplicate_field] = (
        first_user_data[duplicate_field]
    )

    response = http_client.post(
        "/users",
        json=second_user_data,
    )

    assert response.status_code == 409, response.text

    db_session.expire_all()

    users = db_session.query(User).all()

    assert len(users) == 1

    assert users[0].username == "existing_user"
    assert users[0].email == "existing@example.com"


@pytest.mark.parametrize(
    "invalid_field, invalid_value",
    [
        ("username", "ab"),
        ("email", "invalid-email"),
        ("password", "abc123"),
    ],
)
def test_register_user_rejects_invalid_fields(
    db_session,
    http_client,
    invalid_field,
    invalid_value,
):
    registration_data = {
        "username": "validation_user",
        "email": "validation@example.com",
        "password": "UniquePortfolioPass_2026!Q7",
    }

    registration_data[invalid_field] = invalid_value

    response = http_client.post(
        "/users",
        json=registration_data,
    )

    assert response.status_code == 422, response.text

    errors = response.json()["detail"]

    assert any(
        error["loc"] == ["body", invalid_field]
        for error in errors
    )

    db_session.expire_all()

    users = db_session.query(User).all()

    assert users == []


def test_register_user_normalizes_username_and_email(
    db_session,
    http_client,
):
    registration_data = {
        "username": "  Arash_Developer  ",
        "email": "  Arash@EXAMPLE.COM  ",
        "password": "UniquePortfolioPass_2026!Q7",
    }

    response = http_client.post(
        "/users",
        json=registration_data,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["username"] == "arash_developer"
    assert data["email"] == "arash@example.com"

    db_session.expire_all()

    saved_user = (
        db_session.query(User)
        .filter(
            User.username == "arash_developer"
        )
        .one()
    )

    assert saved_user.email == "arash@example.com"

    assert "password" not in data
    assert "hashed_password" not in data


def test_register_user_normalizes_username_and_email(
    db_session,
    http_client,
):
    registration_data = {
        "username": "  Arash_Developer  ",
        "email": "  Arash@EXAMPLE.COM  ",
        "password": "UniquePortfolioPass_2026!Q7",
    }

    response = http_client.post(
        "/users",
        json=registration_data,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["username"] == "arash_developer"
    assert data["email"] == "arash@example.com"

    db_session.expire_all()

    saved_user = (
        db_session.query(User)
        .filter(
            User.username == "arash_developer"
        )
        .one()
    )

    assert saved_user.email == "arash@example.com"

    assert "password" not in data
    assert "hashed_password" not in data


@pytest.mark.parametrize(
    "common_password",
    [
        "password1234",
        "qwerty123456",
        "admin12345678",
        "PASSWORD123",
        "  password123  ",
    ],
)
def test_register_user_rejects_common_passwords(
    db_session,
    http_client,
    common_password
):

    registration_data = {
        "username": "common_password_user",
        "email": "common_password@example.com",
        "password": common_password
    }

    response = http_client.post(
        "/users",
        json= registration_data
    )

    assert response.status_code == 422, response.text

    errors = response.json()["detail"]

    assert any(
        error["loc"] == ["body", "password"]
        for error in errors
    )
    
    db_session.expire_all()

    users = db_session.query(User).all()

    assert users == []

def test_login_user_success(
    db_session,
    http_client,
):

    registration_data = {
        "username": "login_test_user",
        "email": "login_test@example.com",
        "password": "UniqueLoginPassword_2026!Q7",
    }

    register_response = http_client.post(
        "/users",
        json=registration_data,
    )

    assert register_response.status_code == 201, (
        register_response.text
    )

    login_response = http_client.post(
        "/users/login",
        data={
            "username": registration_data["username"],
            "password": registration_data["password"],
        },
    )

    assert login_response.status_code == 200, (
        login_response.text
    )

    data = login_response.json()

    assert data["token_type"] == "bearer"

    assert isinstance(data["access_token"], str)
    assert isinstance(data["refresh_token"], str)

    assert data["access_token"]
    assert data["refresh_token"]

    assert data["access_token"] != data["refresh_token"]

    assert "password" not in data
    assert "hashed_password" not in data


def test_login_with_wrong_password_is_rejected(
    db_session,
    http_client,
):

    registration_data = {
        "username": "wrong_password_user",
        "email": "wrong_password@example.com",
        "password": "UniqueLoginPassword_2026!Q7",
    }

    register_response = http_client.post(
        "/users",
        json=registration_data,
    )

    assert register_response.status_code == 201, (
        register_response.text
    )

    response = http_client.post(
        "/users/login",
        data={
            "username": registration_data["username"],
            "password": "WrongPassword_2026!Q7",
        },
    )

    assert response.status_code == 401, response.text

    assert (
        response.headers.get("WWW-Authenticate")
        == "Bearer"
    )


    db_session.expire_all()

    refresh_tokens = db_session.query(
        RefreshToken
    ).all()

    assert refresh_tokens == []



def test_login_with_nonexistent_username_is_rejected(
    db_session,
    http_client,
    monkeypatch,
):

    monkeypatch.setitem(
        app.dependency_overrides,
        check_rate_limit,
        lambda: None,
    )

    registration_data = {
        "username": "existing_login_user",
        "email": "existing_login@example.com",
        "password": "UniqueLoginPassword_2026!Q7",
    }

    register_response = http_client.post(
        "/users",
        json=registration_data,
    )

    assert register_response.status_code == 201, (
        register_response.text
    )

    wrong_password_response = http_client.post(
        "/users/login",
        data={
            "username": "existing_login_user",
            "password": "WrongPassword_2026!Q7",
        },
    )

    assert wrong_password_response.status_code == 401, (
        wrong_password_response.text
    )

    response = http_client.post(
        "/users/login",
        data={
            "username": "nonexistent_user",
            "password": "WrongPassword_2026!Q7",
        },
    )

    assert response.status_code == 401, response.text

    assert (
        response.headers.get("WWW-Authenticate")
        == "Bearer"
    )

    assert response.json() == (
        wrong_password_response.json()
    )


    db_session.expire_all()

    refresh_tokens = db_session.query(
        RefreshToken
    ).all()

    assert refresh_tokens == []
