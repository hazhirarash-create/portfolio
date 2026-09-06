from pydantic import (BaseModel,
                      ConfigDict,
                      EmailStr,
                      Field,
                      field_validator
                      )
from datetime import datetime
from utils.normalizers import (normalize_username,
                               normalize_email
                               )
from utils.password_policy import is_common_password
class UserCreate(BaseModel):
    username : str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$"
    )
    email : EmailStr
    password : str = Field(
        min_length=8,
        max_length=128
    )
    @field_validator("username", mode="before")
    @classmethod
    def normalize_username_field(cls, value: str) -> str:
        return normalize_username(value)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_field(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def validate_common_password(cls, value: str) -> str:
        if is_common_password(value):
            raise ValueError(
                "password is too common"
            )
        return value

class UserResponse(BaseModel):
    id : int
    username : str
    email : EmailStr
    is_active : bool
    is_admin : bool
    created_at : datetime

    model_config = ConfigDict(from_attributes=True)

class UserLogin(BaseModel):
    username : str = Field(max_length=50)
    password : str = Field(max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username_field(cls, value: str) -> str:
        return normalize_username(value)

class TokenResponse(BaseModel):
    access_token : str
    token_type : str

class RefreshTokenRequest(BaseModel):
    refresh_token : str

class TokenPairResponse(BaseModel):
    access_token : str
    refresh_token : str
    token_type : str = "bearer"