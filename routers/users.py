from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

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
    user_data : UserLogin,
    db : Session = Depends(get_db)
) -> TokenResponse:

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