from database import Base
from sqlalchemy import (Column,
                        ForeignKey,
                        Integer,
                        String,
                        Text,
                        DateTime,
                        Boolean,
                        Enum as SQLEnum
                        )
from sqlalchemy.orm import relationship
from models.base_model import BaseORMModel
from enum import Enum

class User(BaseORMModel):

    __tablename__ = "users"

    username = Column(String, nullable= False, unique= True)
    email = Column(String, nullable= False, unique= True)
    hashed_password = Column(String, nullable= False)
    is_active = Column(Boolean, nullable= False, default= True)
    is_admin = Column(Boolean, nullable=False, default=False)
    refresh_tokens = relationship("RefreshToken",
                                  back_populates="user",
                                  )

class Project(BaseORMModel):

    __tablename__ = "projects"

    title = Column(String, nullable= False)
    description = Column(Text)
    github_url = Column(String, nullable= False)
    demo_url = Column(String)
    is_published = Column(Boolean, default= False)
    images = relationship("Image",
                          back_populates="project",
                          cascade="all,delete-orphan"
                          )

class Image(Base):

    __tablename__ = "images"

    id = Column(Integer, primary_key= True)
    url = Column(String, nullable= False)
    project_id = Column(Integer,ForeignKey("projects.id"))
    project = relationship("Project",back_populates="images")

class RefreshTokenStatus(str, Enum):
    ACTIVE = "active"
    USED = "used"
    REVOKED = "revoked"
    
class RefreshToken(BaseORMModel):

    __tablename__ = "refresh_tokens"

    jti = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    family_id = Column(
        String,
        nullable=False,
        index=True
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False
    )

    status = Column(
    SQLEnum(
        RefreshTokenStatus,
        name="refresh_token_status",
        native_enum=False,
        values_callable=lambda enum_cls: [
            member.value
            for member in enum_cls
        ],
        create_constraint=True,
    ),
    nullable=False,
    default=RefreshTokenStatus.ACTIVE,
    )

    used_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    user = relationship("User",
                        back_populates="refresh_tokens"
                        )