from fastapi import APIRouter, Depends, Query
from schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse
)
from sqlalchemy.orm import Session
from database import get_db
from models.models import Project
from services import project_service

router = APIRouter(
    prefix="/projects",
    tags=["projects"]
)


@router.get(
    "",
    response_model= ProjectListResponse
)
def get_projects(
    page: int = Query(1, ge=1),
    limit: int = Query(10, le=100),
    db: Session = Depends(get_db)
):

    projects, total = project_service.get_projects(page=page, limit=limit, db=db)

    return ProjectListResponse(
    projects=projects,
    total=total,
    page=page,
    limit=limit
)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db:Session=Depends(get_db)):
    project = project_service.get_project_by_id(
    project_id=project_id,
    db=db
    )
    return project


@router.post("", response_model= ProjectResponse)
def create_project(project: ProjectCreate, db: Session= Depends(get_db)):
    new_project = project_service.create_project(project=project, db=db)
    return new_project


@router.patch("/{project_id}", response_model= ProjectResponse)
def update_project(project_id : int,
                   project: ProjectUpdate,
                   db: Session = Depends(get_db)
                   ):
    existing_project = project_service.update_project(
         project_id=project_id,
        project=project,
        db=db
        )
    return existing_project



@router.delete("/{project_id}")
def delete_project(project_id: int,
                  db: Session=Depends(get_db)
                  ):
    existing_project = project_service.delete_project(
         project_id= project_id,
         db = db
    )
    return {
    "message": "project deleted successfully"
}
    