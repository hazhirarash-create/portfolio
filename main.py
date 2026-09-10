from fastapi import FastAPI

from exception_handlers import (
    email_already_exists_handler,
    project_not_found_handler,
    username_already_exists_handler,
    user_already_exists_handler,
    inactive_user_handler,
    invalid_credentials_handler,
    invalid_token_handler,
    admin_access_required_handler,
    compromised_password_handler,
    refresh_token_reuse_handler
    
)
from exceptions.project import ProjectNotFoundError
from exceptions.user import (
    EmailAlreadyExistsError,
    UsernameAlreadyExistsError,
    UserAlreadyExistsError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    AdminAccessRequiredError,
    CompromisedPasswordError,
    RefreshTokenReuseDetectedError
)
from routers import projects, users

from core.logging_config import setup_logging


app = FastAPI()

setup_logging()

app.include_router(projects.router)
app.include_router(users.router)

app.add_exception_handler(
    ProjectNotFoundError,
    project_not_found_handler
)

app.add_exception_handler(
    UsernameAlreadyExistsError,
    username_already_exists_handler
)

app.add_exception_handler(
    EmailAlreadyExistsError,
    email_already_exists_handler
)

app.add_exception_handler(
    UserAlreadyExistsError,
    user_already_exists_handler
)

app.add_exception_handler(
    InvalidCredentialsError,
    invalid_credentials_handler
)

app.add_exception_handler(
    InactiveUserError,
    inactive_user_handler
)

app.add_exception_handler(
    InvalidTokenError,
    invalid_token_handler
)

app.add_exception_handler(
    AdminAccessRequiredError,
    admin_access_required_handler
)

app.add_exception_handler(
    CompromisedPasswordError,
    compromised_password_handler
)

app.add_exception_handler(
    RefreshTokenReuseDetectedError,
    refresh_token_reuse_handler
)