from fastapi import Request, status
from fastapi.responses import JSONResponse

from exceptions.project import ProjectNotFoundError

from exceptions.user import (UsernameAlreadyExistsError,
                             EmailAlreadyExistsError,
                             UserAlreadyExistsError,
                             InactiveUserError,
                             InvalidCredentialsError,
                             InvalidTokenError,
                             AdminAccessRequiredError)


async def project_not_found_handler(
    _request: Request,
    exc: ProjectNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": str(exc)
        }
    )

async def username_already_exists_handler(
        _request: Request,
        exc: UsernameAlreadyExistsError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail":str(exc)
        }
    )

async def email_already_exists_handler(
        _request: Request,
        exc: EmailAlreadyExistsError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": str(exc)
        }
    ) 

async def user_already_exists_handler(
        _request: Request,
        exc: UserAlreadyExistsError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": str(exc)
        }
    )

async def invalid_credentials_handler(
        _request: Request,
        exc: InvalidCredentialsError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "detail": str(exc)
        },
        headers={
            "WWW-Authenticate": "Bearer"
        }
    )

async def inactive_user_handler(
        _request: Request,
        exc: InactiveUserError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "detail": str(exc)
        }
    )

async def invalid_token_handler(
        _request: Request,
        exc: InvalidTokenError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "detail": str(exc)
        },
        headers={
            "WWW-Authenticate": "Bearer"
        }
    )

async def admin_access_required_handler(
        _request: Request,
        exc: AdminAccessRequiredError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "detail": str(exc)
        }
    )