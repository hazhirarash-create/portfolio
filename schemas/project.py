from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    HttpUrl,
    ValidationInfo,
)
from datetime import datetime

class ProjectValidationMixin:

    @field_validator("title", check_fields=False)
    @classmethod
    def validate_title(cls, value):
        if value is None:
            return value

        if not value.strip():
            raise ValueError(
                "Project title cannot be empty"
            )

        return value.strip()

    @field_validator("github_url", check_fields=False)
    @classmethod
    def validate_github_url(cls, value):
        if value is None:
            return value

        url = HttpUrl(value)

        if url.scheme != "https":
            raise ValueError(
                "Github URL must use HTTPS"
            )

        if url.host not in ("github.com", "www.github.com"):
            raise ValueError(
                "GitHub URL must use github.com"
            )

        path_parts = [
        part
        for part in url.path.strip("/").split("/")
        if part
    ]

        if len(path_parts) != 2:
            raise ValueError(
                "GitHub URL must point to a repository"
            )

        return str(url)

class ImageResponse(BaseModel):
    id: int
    url: str

    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(ProjectValidationMixin, BaseModel):
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


class ProjectUpdate(ProjectValidationMixin, BaseModel):
    title: str | None = None
    description: str | None = None
    github_url: str | None = None
    demo_url: str | None = None
    is_published: bool | None = None

    @field_validator(
        "title",
        "github_url",
        "is_published",
        mode="before",
    )
    @classmethod
    def reject_null_for_required_fields(cls, value):
        if value is None:
            raise ValueError(
                "This field cannot be null"
            )

        return value