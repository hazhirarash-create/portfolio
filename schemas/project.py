from pydantic import BaseModel, ConfigDict
from datetime import datetime


class ImageResponse(BaseModel):
    id: int
    url: str

    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    title: str
    description: str | None = None
    github_url: str
    model_config = ConfigDict(from_attributes=True)

class ProjectResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    github_url: str
    demo_url: str | None = None
    created_at: datetime
    updated_at: datetime
    is_published: bool
    images: list[ImageResponse] = []

    model_config = ConfigDict(from_attributes=True)

class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int
    page: int
    limit: int    
    model_config = ConfigDict(from_attributes=True)


class ProjectUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    github_url: str | None = None
    demo_url: str | None = None
    is_published: bool | None = None
    model_config = ConfigDict(from_attributes=True)