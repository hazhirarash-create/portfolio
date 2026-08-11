from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime

class UserCreate(BaseModel):
    username : str
    email : EmailStr
    password : str

class UserResponse(BaseModel):
    id : int
    username : str
    email : EmailStr
    is_active : bool
    is_admin : bool
    created_at : datetime

    model_config = ConfigDict(from_attributes=True)

class UserLogin(BaseModel):
    username : str
    password : str