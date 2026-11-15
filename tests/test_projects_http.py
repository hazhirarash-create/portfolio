from models.models import Project, Image
from security.jwt_handler import create_access_token
from sqlalchemy.orm import Session
import pytest

def test_get_projects_http_returns_published_projects_with_images(
        db_session,
        http_client
):

    published_project = Project(
        title = "FastAPI Portfolio",
        github_url = "https://github.com/example/portfolio",
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

def test_create_project_without_token_is_rejected(
        db_session,
        http_client
):
    response = http_client.post(
        "/projects",
        json = {
            "title": "Unauthrized Project",
            "github_url": "https://github.com/example/unauthorized"
        }
    )

    assert response.status_code == 401

    assert (
        response.headers.get("WWW-Authenticate")
        == "Bearer"
    )

    projects = db_session.query(Project).all()

    assert projects == []

def test_create_project_as_regular_user_is_forbidden(
        db_session,
        http_client,
        test_user
):

    access_token = create_access_token(
        user_id= test_user.id
    )

    response = http_client.post(
        "/projects",
        headers= {
            "Authorization": f"Bearer {access_token}"
        },

        json= {
            "title": "Forbiden Project",
            "github_url": "https://github.com/example/forbiden"
        }
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": "Admin access required"
    }

    projects = db_session.query(Project).all()

    assert projects == []


def test_create_project_as_admin_succeeds(
        db_session,
        http_client,
        test_user
):

    test_user.is_admin = True
    db_session.commit()

    access_token = create_access_token(
        user_id=test_user.id
    )

    response = http_client.post(
        "/projects",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        json={
            "title": "Admin Project",
            "description": "Created through HTTP test",
            "github_url": "https://github.com/example/admin-project"
        }
    )

    assert response.status_code == 201

    data = response.json()

    assert isinstance(data["id"], int)
    assert data["title"] == "Admin Project"
    assert data["description"] == "Created through HTTP test"
    assert data["github_url"] == (
        "https://github.com/example/admin-project"
    )
    assert data["is_published"] is False
    assert data["images"] == []

    db_session.expire_all()

    project_record = (
        db_session.query(Project)
        .filter(Project.id == data["id"])
        .one()
    )

    assert project_record.title == "Admin Project"
    assert project_record.description == (
        "Created through HTTP test"
    )
    assert project_record.is_published is False


def test_get_nonexistent_project_returns_404(
        http_client
):

    response = http_client.get(
        "/projects/99999999"   
    )

    assert response.status_code == 404

    data = response.json()

    assert "detail" in data
    assert isinstance(data["detail"], str)
    assert data["detail"]

def test_get_existing_project_by_id_returns_project_with_images(
    db_session,
    http_client,
):
    project = Project(
        title="FastAPI Portfolio Detail",
        description="Project details HTTP test",
        github_url="https://github.com/example/detail",
        is_published=True,
    )

    db_session.add(project)
    db_session.flush()

    project_id = project.id

    db_session.add(
        Image(
            url="/images/detail.png",
            project_id=project_id,
        )
    )

    db_session.commit()

    response = http_client.get(
        f"/projects/{project_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == project_id
    assert data["title"] == "FastAPI Portfolio Detail"
    assert data["description"] == "Project details HTTP test"
    assert data["github_url"] == (
        "https://github.com/example/detail"
    )
    assert data["is_published"] is True

    assert len(data["images"]) == 1
    assert data["images"][0]["url"] == "/images/detail.png"

    assert "created_at" in data
    assert "updated_at" in data

def test_update_project_as_admin_changes_only_provided_fields(
    db_session,
    http_client,
    test_user,
):
    project = Project(
        title="Original Title",
        description="Original Description",
        github_url="https://github.com/example/original",
        is_published=True,
    )

    db_session.add(project)
    db_session.commit()

    project_id = project.id

    test_user.is_admin = True
    db_session.commit()

    access_token = create_access_token(
        user_id=test_user.id,
    )

    response = http_client.patch(
        f"/projects/{project_id}",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        json={
            "title": "Updated Title",
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["id"] == project_id
    assert data["title"] == "Updated Title"
    assert data["description"] == "Original Description"
    assert data["github_url"] == (
        "https://github.com/example/original"
    )
    assert data["is_published"] is True

    db_session.expire_all()

    updated_project = db_session.get(
        Project,
        project_id,
    )

    assert updated_project is not None
    assert updated_project.title == "Updated Title"
    assert updated_project.description == (
        "Original Description"
    )
    assert updated_project.github_url == (
        "https://github.com/example/original"
    )
    assert updated_project.is_published is True

def test_update_project_as_regular_user_is_forbidden(
    db_session,
    http_client,
    test_user,
):
    project = Project(
        title="Protected Project",
        description="Must remain unchanged",
        github_url="https://github.com/example/protected",
        is_published=False,
    )

    db_session.add(project)
    db_session.commit()

    project_id = project.id

    assert test_user.is_admin is False

    access_token = create_access_token(
        user_id=test_user.id,
    )

    response = http_client.patch(
        f"/projects/{project_id}",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        json={
            "title": "Unauthorized Change",
        },
    )

    assert response.status_code == 403, response.text

    assert response.json() == {
        "detail": "Admin access required"
    }

    db_session.expire_all()

    unchanged_project = db_session.get(
        Project,
        project_id,
    )

    assert unchanged_project is not None
    assert unchanged_project.title == "Protected Project"
    assert unchanged_project.description == (
        "Must remain unchanged"
    )
    assert unchanged_project.is_published is False

def test_update_project_without_token_is_rejected(
    db_session,
    http_client,
):

    project = Project(
        title="Original Project",
        description="Must stay unchanged",
        github_url="https://github.com/example/original",
        is_published=False,
    )

    db_session.add(project)
    db_session.commit()

    project_id = project.id

    response = http_client.patch(
        f"/projects/{project_id}",
        json={
            "title": "Unauthorized Update",
        },
    )

    assert response.status_code == 401, response.text

    assert (
        response.headers.get("WWW-Authenticate")
        == "Bearer"
    )

    db_session.expire_all()

    unchanged_project = db_session.get(
        Project,
        project_id,
    )

    assert unchanged_project is not None
    assert unchanged_project.title == "Original Project"
    assert unchanged_project.description == (
        "Must stay unchanged"
    )
    assert unchanged_project.is_published is False

def test_delete_draft_project_as_admin_removes_images(
    db_session,
    http_client,
    test_user,
):

    project = Project(
        title="Draft Project",
        description="Project to delete",
        github_url="https://github.com/example/delete",
        is_published=False,
    )

    db_session.add(project)
    db_session.flush()

    project_id = project.id

    image_1 = Image(
        url="/images/delete-1.png",
        project_id=project_id,
    )

    image_2 = Image(
        url="/images/delete-2.png",
        project_id=project_id,
    )

    db_session.add_all([image_1, image_2])
    db_session.commit()

    assert db_session.get(Project, project_id) is not None

    assert (
        db_session.query(Image)
        .filter_by(project_id=project_id)
        .count()
        == 2
    )

    test_user.is_admin = True
    db_session.commit()

    access_token = create_access_token(
        user_id=test_user.id,
    )

    response = http_client.delete(
        f"/projects/{project_id}",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 200, response.text

    db_session.expire_all()

    deleted_project = db_session.get(
        Project,
        project_id,
    )

    assert deleted_project is None

    remaining_images = (
        db_session.query(Image)
        .filter_by(project_id=project_id)
        .all()
    )

    assert remaining_images == []

def test_delete_project_as_regular_user_is_forbidden(
        db_session,
        test_user,
        http_client
):

    project = Project(
        title="Protected Project",
        description="Must not be deleted",
        github_url="https://github.com/example/protected",
        is_published=False,
    )

    db_session.add(project)
    db_session.flush()

    project_id = project.id

    image = Image(
        url = "/images/protected.png",
        project_id = project_id
    )

    db_session.add(image)
    db_session.commit()

    assert test_user.is_admin is False

    access_token = create_access_token(
        user_id=test_user.id,
    )

    response = http_client.delete(
        f"/projects/{project_id}",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 403, response.text

    assert response.json() == {
        "detail": "Admin access required"
    }

    db_session.expire_all()

    unchanged_project = db_session.get(
        Project,
        project_id,
    )

    assert unchanged_project is not None
    assert unchanged_project.title == "Protected Project"
    assert unchanged_project.is_published is False

    remaining_images = (
        db_session.query(Image)
        .filter_by(project_id=project_id)
        .all()
    )

    assert len(remaining_images) == 1
    assert remaining_images[0].url == "/images/protected.png"

def test_delete_project_without_token_is_rejected(
    db_session,
    http_client,
):
    project = Project(
        title="Protected Draft",
        description="Must not be deleted",
        github_url="https://github.com/example/protected-draft",
        is_published=False,
    )

    db_session.add(project)
    db_session.flush()

    project_id = project.id

    image = Image(
        url="/images/protected-draft.png",
        project_id=project_id,
    )

    db_session.add(image)
    db_session.commit()

    response = http_client.delete(
        f"/projects/{project_id}",
    )

    assert response.status_code == 401, response.text

    assert (
        response.headers.get("WWW-Authenticate")
        == "Bearer"
    )

    db_session.expire_all()

    unchanged_project = db_session.get(
        Project,
        project_id,
    )

    assert unchanged_project is not None
    assert unchanged_project.title == "Protected Draft"
    assert unchanged_project.is_published is False

    remaining_images = (
        db_session.query(Image)
        .filter_by(project_id=project_id)
        .all()
    )

    assert len(remaining_images) == 1
    assert remaining_images[0].url == (
        "/images/protected-draft.png"
    )

def test_delete_nonexistent_project_as_admin_returns_404(
    db_session,
    http_client,
    test_user,
):

    test_user.is_admin = True
    db_session.commit()

    access_token = create_access_token(
        user_id=test_user.id,
    )

    response = http_client.delete(
        "/projects/999999",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 404, response.text

    assert response.json() == {
        "detail": "Project 999999 not found"
    }

    projects = db_session.query(Project).all()

    assert projects == []

def test_update_nonexistent_project_as_admin_returns_404(
    db_session,
    http_client,
    test_user,
):

    test_user.is_admin = True
    db_session.commit()

    access_token = create_access_token(
        user_id=test_user.id,
    )

    response = http_client.patch(
        "/projects/999999",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        json={
            "title": "Updated Nonexistent Project",
        },
    )

    assert response.status_code == 404, response.text

    assert response.json() == {
        "detail": "Project 999999 not found"
    }

    projects = db_session.query(Project).all()

    assert projects == []

@pytest.mark.parametrize(
    "invalid_field",
    [
        "title",
        "github_url",
        "is_published",
    ],
)
def test_update_project_rejects_null_for_required_fields(
    db_session,
    http_client,
    test_user,
    invalid_field,
):

    project = Project(
        title="Original Title",
        description="Original Description",
        github_url="https://github.com/example/original",
        is_published=False,
    )

    db_session.add(project)
    db_session.commit()

    project_id = project.id

    test_user.is_admin = True
    db_session.commit()

    access_token = create_access_token(
        user_id=test_user.id,
    )

    response = http_client.patch(
        f"/projects/{project_id}",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        json={
            invalid_field: None,
        },
    )

    assert response.status_code == 422, response.text

    errors = response.json()["detail"]

    assert any(
        error["loc"] == ["body", invalid_field]
        for error in errors
    )

    db_session.expire_all()

    unchanged_project = db_session.get(
        Project,
        project_id,
    )

    assert unchanged_project is not None
    assert unchanged_project.title == "Original Title"
    assert unchanged_project.description == "Original Description"
    assert unchanged_project.github_url == (
        "https://github.com/example/original"
    )
    assert unchanged_project.is_published is False
