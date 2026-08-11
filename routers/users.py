from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from models.models import User
from schemas.user import UserCreate, UserResponse
from services.user_service import create_user


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