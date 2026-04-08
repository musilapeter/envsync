from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.auth import CurrentUser, get_current_user
from backend.app.audit import log_action
from backend.app.db import db
from backend.app.models import EnvVersion

router = APIRouter(prefix="/env", tags=["env"])


class EnvPushPayload(BaseModel):
    ciphertext: str
    key_names: list[str]


@router.post("/{project_id}/{branch}")
async def push_env(
    project_id: str,
    branch: str,
    payload: EnvPushPayload,
    user: CurrentUser = Depends(get_current_user),
):
    """Store an encrypted .env snapshot."""
    if not user.can_write(project_id):
        raise HTTPException(status_code=403, detail="No write access to this project")

    latest = await db.env_versions.find_one(
        {"project_id": project_id, "branch": branch},
        sort=[("version", -1)],
    )
    version = (latest["version"] + 1) if latest else 1

    doc = EnvVersion(
        project_id=project_id,
        branch=branch,
        ciphertext=payload.ciphertext,
        key_names=payload.key_names,
        pushed_by=user.email,
        version=version,
    )
    await db.env_versions.insert_one(doc.model_dump())
    await log_action(user.email, "push", project_id, branch)
    return {"version": version, "message": "Env pushed successfully"}


@router.get("/{project_id}/{branch}")
async def pull_env(
    project_id: str,
    branch: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Fetch the latest encrypted .env snapshot for a branch."""
    latest = await db.env_versions.find_one(
        {"project_id": project_id, "branch": branch},
        sort=[("version", -1)],
    )
    if not latest:
        raise HTTPException(status_code=404, detail="No env found for this branch")

    await log_action(user.email, "pull", project_id, branch)
    return {
        "ciphertext": latest["ciphertext"],
        "key_names": latest["key_names"],
        "version": latest["version"],
        "pushed_by": latest["pushed_by"],
        "pushed_at": latest["pushed_at"],
    }
