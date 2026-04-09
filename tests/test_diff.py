from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from backend.app.auth import CurrentUser, get_current_user
from backend.app.db import db
from backend.app.main import app

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
    return CurrentUser(email="dev@example.com", writable_projects={"project-123"})


@pytest.fixture
def reader_user() -> CurrentUser:
    from backend.app.auth import UserRole
    return CurrentUser(
        email="reader@example.com",
        role=UserRole.READONLY,
        project_ids={"project-123"},
    )


def test_drift_endpoint_compares_local_and_server_keys(writer_user: CurrentUser, reader_user: CurrentUser):
    app.dependency_overrides[get_current_user] = lambda: writer_user
    push_response = client.post(
        "/env/project-123/main",
        json={"ciphertext": "blob-v1", "key_names": ["API_KEY", "DEBUG", "STRIPE_SECRET"]},
    )
    assert push_response.status_code == 200

    app.dependency_overrides[get_current_user] = lambda: reader_user
    response = client.get(
        "/env/project-123/main/diff",
        params=[("local_keys", "API_KEY"), ("local_keys", "EXTRA_ONLY")],
    )

    assert response.status_code == 200
    assert response.json() == {
        "missing_locally": ["DEBUG", "STRIPE_SECRET"],
        "extra_locally": ["EXTRA_ONLY"],
        "in_sync": False,
    }
