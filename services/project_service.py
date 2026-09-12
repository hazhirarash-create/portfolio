from sqlalchemy.orm import Session
from models.models import Project
from schemas.project import ProjectCreate, ProjectUpdate
from exceptions.project_exceptions import ProjectNotFoundError


def get_project_by_id(project_id:int, db:Session):
    project = (db.query(Project).filter_by(id=project_id).first())
    if project is None:
        raise ProjectNotFoundError(project_id)
    return project


def get_projects(page: int, limit:int, db:Session):
    total = (db.query(Project).filter_by(is_published=True).count())
    offset = ((page - 1) * limit)
    projects =( db.query(Project)
               .filter_by(is_published=True)
               .order_by(Project.created_at.desc())
               .limit(limit)
               .offset(offset)
               .all())
    return projects, total


def create_project(project:ProjectCreate, db:Session):
    new_project = Project(**project.model_dump())
    try:
        db.add(new_project)
        db.commit()
        db.refresh(new_project)
    except Exception:
        db.rollback()
        raise
    return new_project


def update_project(project_id: int, project:ProjectUpdate, db: Session):
    existing_project = get_project_by_id(
        project_id=project_id,
        db=db
    )
    update_data = project.model_dump(exclude_unset=True)
    for key,value in update_data.items():
        setattr(existing_project, key, value)
    try:
        db.commit()
        db.refresh(existing_project)
    except Exception:
        db.rollback()
        raise
    return existing_project


def delete_project(project_id: int,
                   db: Session
                   ):
    existing_project = get_project_by_id(
        project_id=project_id,
        db=db
    )
    try:
        db.delete(existing_project)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return existing_project