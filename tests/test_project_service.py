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

def test_get_projects_pagination(db_session):

    for i in range(23):
        project = Project(
            title=f"Project {i}",
            github_url=f"https://github.com/example/project-{i}",
            is_published=True,
        )
        db_session.add(project)

    db_session.add(
        Project(
            title="Unpublished",
            github_url="https://github.com/example/unpublished",
            is_published=False,
        )
    )

    db_session.commit()

    # Act: Fetch three pages
    page_1, total_1 = get_projects(
        page=1,
        limit=10,
        db=db_session,
    )

    page_2, total_2 = get_projects(
        page=2,
        limit=10,
        db=db_session,
    )

    page_3, total_3 = get_projects(
        page=3,
        limit=10,
        db=db_session,
    )

    assert total_1 == 23
    assert total_2 == 23
    assert total_3 == 23

    assert len(page_1) == 10
    assert len(page_2) == 10
    assert len(page_3) == 3

    ids_1 = {project.id for project in page_1}
    ids_2 = {project.id for project in page_2}
    ids_3 = {project.id for project in page_3}

    assert ids_1.isdisjoint(ids_2)
    assert ids_1.isdisjoint(ids_3)
    assert ids_2.isdisjoint(ids_3)

    all_projects = page_1 + page_2 + page_3

    assert all(project.is_published for project in all_projects)