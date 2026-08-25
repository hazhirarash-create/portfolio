from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import ValidationError

from database import get_db
from models.models import User
from schemas.user import (UserCreate,
                          UserResponse,
                          TokenResponse,
                          UserLogin
                          )
from services.user_service import (create_user,
                                   authenticate_user
                                   )

from security.jwt_handler import create_access_token
from dependencies.auth import (get_current_user,
                               )

from fastapi.security import OAuth2PasswordRequestForm

from security.rate_limit import check_rate_limit


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
) -> User:
    return create_user(
        user_data=user_data,
        db=db
    )

@router.post(
    "/login",
    response_model=TokenResponse
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    _: None = Depends(check_rate_limit),
    db: Session = Depends(get_db)
) -> TokenResponse:
    
    try:
        user_data = UserLogin(
            username=form_data.username,
            password=form_data.password
        )

    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors()
        ) from exc

    user = authenticate_user(
        user_data=user_data,
        db=db
    )

    access_token = create_access_token(
        user_id=user.id
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer"
    )

@router.get(
    "/me",
    response_model=UserResponse
)
def get_me(
    current_user: User = Depends(get_current_user)
) -> User:
    return current_user