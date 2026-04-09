from __future__ import annotations

import jwt
import pytest
from fastapi.testclient import TestClient

from backend.app.db import db
from backend.app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    monkeypatch.setenv("ENVSYNC_JWT_SECRET", "test-secret")
    monkeypatch.setenv("ENVSYNC_JWT_ALGORITHM", "HS256")
    db.env_versions.clear()
    db.audits.clear()
    app.dependency_overrides.clear()
    yield
    db.env_versions.clear()
    db.audits.clear()
    app.dependency_overrides.clear()


def _make_token(email: str, role: str, project_ids: list[str] | None = None) -> str:
    payload: dict[str, object] = {"email": email, "role": role}
    if project_ids is not None:
        payload["project_ids"] = project_ids
    return jwt.encode(payload, "test-secret", algorithm="HS256")


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_missing_token_returns_401():
    response = client.get("/env/project-123/main")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_invalid_token_returns_401():
    response = client.get(
        "/env/project-123/main",
        headers=_auth_header("not-a-valid-jwt"),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


def test_readonly_can_read_but_cannot_push():
    owner_token = _make_token("owner@example.com", "owner")
    readonly_token = _make_token("readonly@example.com", "readonly", ["project-123"])

    push = client.post(
        "/env/project-123/main",
        json={"ciphertext": "blob-v1", "key_names": ["API_KEY", "DEBUG"]},
        headers=_auth_header(owner_token),
    )
    assert push.status_code == 200

    readonly_push = client.post(
        "/env/project-123/main",
        json={"ciphertext": "blob-v2", "key_names": ["API_KEY"]},
        headers=_auth_header(readonly_token),
    )
    assert readonly_push.status_code == 403
    assert readonly_push.json()["detail"] == "No write access to this project"

    readonly_pull = client.get("/env/project-123/main", headers=_auth_header(readonly_token))
    assert readonly_pull.status_code == 200

    readonly_diff = client.get(
        "/env/project-123/main/diff",
        params=[("local_keys", "API_KEY")],
        headers=_auth_header(readonly_token),
    )
    assert readonly_diff.status_code == 200


def test_developer_cannot_access_unassigned_project():
    owner_token = _make_token("owner@example.com", "owner")
    developer_token = _make_token("dev@example.com", "developer", ["project-123"])

    seeded = client.post(
        "/env/project-999/main",
        json={"ciphertext": "blob-v1", "key_names": ["API_KEY"]},
        headers=_auth_header(owner_token),
    )
    assert seeded.status_code == 200

    pull = client.get("/env/project-999/main", headers=_auth_header(developer_token))
    assert pull.status_code == 403
    assert pull.json()["detail"] == "No read access to this project"

    push = client.post(
        "/env/project-999/main",
        json={"ciphertext": "blob-v2", "key_names": ["API_KEY"]},
        headers=_auth_header(developer_token),
    )
    assert push.status_code == 403
    assert push.json()["detail"] == "No write access to this project"


def test_owner_can_access_any_project_without_project_list():
    owner_token = _make_token("owner@example.com", "owner")

    push = client.post(
        "/env/project-abc/main",
        json={"ciphertext": "blob-v1", "key_names": ["API_KEY"]},
        headers=_auth_header(owner_token),
    )
    assert push.status_code == 200

    pull = client.get("/env/project-abc/main", headers=_auth_header(owner_token))
    assert pull.status_code == 200
