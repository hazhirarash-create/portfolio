from sqlalchemy import event, select
from models.models import Project, Image
from sqlalchemy.orm import Session, selectinload


def test_count_project_queries(db_session):
    statements = []

    engine = db_session.get_bind()

    def capture_sql(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        statements.append(statement)

    event.listen(
        engine,
        "before_cursor_execute",
        capture_sql,
    )

    try:
        db_session.execute(
            select(Project)
        ).all()

    finally:
        event.remove(
            engine,
            "before_cursor_execute",
            capture_sql,
        )

    print("SQL statements:", len(statements))

    for statement in statements:
        print(statement)

    assert len(statements) == 1


def test_lazy_loading_causes_n_plus_one(db_session):

    for i in range(3):
        project = Project(
            title=f"Project {i}",
            github_url=f"https://github.com/example/project-{i}",
            is_published=True,
        )

        db_session.add(project)
        db_session.flush()

        image = Image(
            url=f"/images/project-{i}.png",
            project_id=project.id,
        )

        db_session.add(image)

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
            projects = (
                query_db.query(Project)
                .order_by(Project.id)
                .all()
            )

            for project in projects:
                print(project.images)

        finally:
            event.remove(
                engine,
                "before_cursor_execute",
                capture_sql,
            )

    print("Total SQL queries:", len(statements))

    assert len(statements) == 4

def test_selectinload_avoids_n_plus_one(db_session):

    for i in range(3):
        project = Project(
            title=f"Project {i}",
            github_url=f"https://github.com/example/project-{i}",
            is_published=True,
        )

        db_session.add(project)
        db_session.flush()

        db_session.add(
            Image(
                url=f"/images/project-{i}.png",
                project_id=project.id,
            )
        )

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
            projects = (
                query_db.query(Project)
                .options(selectinload(Project.images))
                .order_by(Project.id)
                .all()
            )

            for project in projects:
                print(
                    project.title,
                    [image.url for image in project.images],
                )

        finally:
            event.remove(
                engine,
                "before_cursor_execute",
                capture_sql,
            )

    print("Total SQL queries with selectinload:", len(statements))

    assert len(projects) == 3
    assert len(statements) == 2