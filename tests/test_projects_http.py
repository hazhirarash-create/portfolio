from models.models import Project, Image

def test_get_projects_http_returns_published_projects_with_images(
        db_session,
        http_client
):

    published_project = Project(
        title = "FastAPI Portfolio",
        github_url = "https://github.con/example/portfolio",
        is_published = True
    )

    db_session.add(published_project)
    db_session.flush()

    db_session.add(
        Image(
            url = "/images/portfolio.png",
            project_id = published_project.id
        )
    )

    db_session.add(
        Project(
            title = "unpublished",
            github_url = "https://github.com/example/unpublished",
            is_published = False
        )
    )

    db_session.commit()

    response = http_client.get(
        "/projects",
        params={
            "page": 1,
            "limit": 10,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["page"] == 1
    assert data["limit"] == 10

    assert len(data["projects"]) == 1

    project_data = data["projects"][0]

    assert project_data["title"] == "FastAPI Portfolio"
    assert project_data["is_published"] is True

    assert len(project_data["images"]) == 1
    assert project_data["images"][0]["url"] == "/images/portfolio.png"

def test_get_projects_rejects_invalid_limit(http_client):

    invalid_limits = [0, -1, 101]

    for limit in invalid_limits:
        response = http_client.get(
            "/projects",
            params={
                "page": 1,
                "limit": limit,
            },
        )

        assert response.status_code == 422, (
            f"Expected 422 for limit={limit}, "
            f"got {response.status_code}"
        )

def test_get_projects_rejects_invalid_page(http_client):

    invalid_pages = [0, -1, -10]

    for page in invalid_pages:
        response = http_client.get(
            "/projects",
            params={
                "page": page,
                "limit": 10
            },
        )

        assert response.status_code == 422, (
            f"Expected 422 for page={page}",
            f"got {response.status_code}"
        )