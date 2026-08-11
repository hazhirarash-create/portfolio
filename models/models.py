from database import Base
from sqlalchemy import Column, ForeignKey, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from models.base_model import BaseORMModel

class User(BaseORMModel):

    __tablename__ = "users"

    username = Column(String, nullable= False, unique= True)
    email = Column(String, nullable= False, unique= True)
    hashed_password = Column(String, nullable= False)
    is_active = Column(Boolean, nullable= False, default= True)
    is_admin = Column(Boolean, nullable=False, default=False)

class Project(BaseORMModel):

    __tablename__ = "projects"

    title = Column(String, nullable= False)
    description = Column(Text)
    github_url = Column(String, nullable= False)
    demo_url = Column(String)
    is_published = Column(Boolean, default= False)
    images = relationship("Image",back_populates="project", cascade= "all, delete-orphan")

class Image(Base):

    __tablename__ = "images"

    id = Column(Integer, primary_key= True)
    url = Column(String, nullable= False)
    project_id = Column(Integer,ForeignKey("projects.id"))
    project = relationship("Project",back_populates="images")