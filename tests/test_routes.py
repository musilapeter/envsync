from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from backend.app.auth import CurrentUser, get_current_user
from backend.app.main import app
from backend.app.db import db

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    db.env_versions.clear()
    db.audits.clear()
    app.dependency_overrides.clear()
    yield
    db.env_versions.clear()
    db.audits.clear()
    app.dependency_overrides.clear()


@pytest.fixture
def writer_user() -> CurrentUser:
    from backend.app.auth import UserRole
    return CurrentUser(
        email="dev@example.com",
        role=UserRole.DEVELOPER,
        project_ids={"project-123"},
    )


@pytest.fixture
def reader_user() -> CurrentUser:
    from backend.app.auth import UserRole
    return CurrentUser(
        email="reader@example.com",
        role=UserRole.READONLY,
        project_ids={"project-123"},
    )


def test_push_and_pull_latest_snapshot(writer_user: CurrentUser):
    app.dependency_overrides[get_current_user] = lambda: writer_user

    push_response = client.post(
        "/env/project-123/main",
        json={"ciphertext": "blob-v1", "key_names": ["API_KEY", "DEBUG"]},
    )

    assert push_response.status_code == 200
    assert push_response.json() == {"version": 1, "message": "Env pushed successfully"}
    assert len(db.env_versions.documents) == 1
    assert len(db.audits.documents) == 1
    assert db.audits.documents[0]["action"] == "push"

    pull_response = client.get("/env/project-123/main")

    assert pull_response.status_code == 200
    assert pull_response.json()["ciphertext"] == "blob-v1"
    assert pull_response.json()["key_names"] == ["API_KEY", "DEBUG"]
    assert pull_response.json()["version"] == 1
    assert len(db.audits.documents) == 2
    assert db.audits.documents[1]["action"] == "pull"


def test_push_rejects_writers_without_access(reader_user: CurrentUser):
    app.dependency_overrides[get_current_user] = lambda: reader_user

    response = client.post(
        "/env/project-123/main",
        json={"ciphertext": "blob-v1", "key_names": ["API_KEY"]},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "No write access to this project"
    assert db.env_versions.documents == []
    assert db.audits.documents == []


def test_readonly_can_pull_and_diff(writer_user: CurrentUser, reader_user: CurrentUser):
    app.dependency_overrides[get_current_user] = lambda: writer_user
    push_response = client.post(
        "/env/project-123/main",
        json={"ciphertext": "blob-v1", "key_names": ["API_KEY", "DEBUG"]},
    )
    assert push_response.status_code == 200

    app.dependency_overrides[get_current_user] = lambda: reader_user
    pull_response = client.get("/env/project-123/main")
    assert pull_response.status_code == 200
    assert pull_response.json()["ciphertext"] == "blob-v1"
    assert pull_response.json()["key_names"] == ["API_KEY", "DEBUG"]

    diff_response = client.get(
        "/env/project-123/main/diff",
        params=[("local_keys", "API_KEY")],
    )
    assert diff_response.status_code == 200
    assert diff_response.json()["missing_locally"] == ["DEBUG"]
    assert diff_response.json()["extra_locally"] == []
