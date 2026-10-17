from sqlalchemy import event
from sqlalchemy.orm import Session

from models.models import Project, Image
from services.project_service import get_projects

def test_get_projects_avoids_n_plus_one(db_session):

    for i in range(3):
        project = Project(
            title = f"project-{i}",
            github_url = f"https://github.com/example/project-{i}",
            is_published = True
        )

        db_session.add(project)
        db_session.flush()

        image = Image(
            url = f"/images/project-{i}.png",
            project_id = project.id
        )

        db_session.add(image)

    unpublished_project = Project(
        title="Unpublished Project",
        github_url="https://github.com/example/unpublished",
        is_published=False,
    )

    db_session.add(unpublished_project)
    db_session.commit()

    engine = db_session.get_bind()
    statements = []

    def capture_sql(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        statements.append(statement)

    with Session(bind=engine) as query_db:
        event.listen(
            engine,
            "before_cursor_execute",
            capture_sql,
        )

        try:
            projects, total = get_projects(
                page=1,
                limit=10,
                db=query_db,
            )

            # Access images while counting queries
            image_urls = [
                image.url
                for project in projects
                for image in project.images
            ]

        finally:
            event.remove(
                engine,
                "before_cursor_execute",
                capture_sql,
            )

    assert total == 3
    assert len(projects) == 3
    assert all(project.is_published for project in projects)
    assert len(image_urls) == 3

    assert len(statements) == 3