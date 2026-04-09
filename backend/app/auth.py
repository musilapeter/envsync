from __future__ import annotations

import os
from enum import Enum

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field


class UserRole(str, Enum):
    OWNER = "owner"
    DEVELOPER = "developer"
    READONLY = "readonly"


bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    email: str
    role: UserRole = UserRole.DEVELOPER
    project_ids: set[str] = Field(default_factory=set)
    writable_projects: set[str] = Field(default_factory=set)

    def _allowed_projects(self) -> set[str]:
        return self.project_ids | self.writable_projects

    def can_read(self, project_id: str) -> bool:
        if self.role == UserRole.OWNER:
            return True
        return project_id in self._allowed_projects()

    def can_write(self, project_id: str) -> bool:
        if self.role == UserRole.OWNER:
            return True
        if self.role == UserRole.READONLY:
            return False
        return project_id in self._allowed_projects()


def _get_jwt_settings() -> tuple[str, str]:
    secret = os.getenv("ENVSYNC_JWT_SECRET", "dev-secret-change-me")
    algorithm = os.getenv("ENVSYNC_JWT_ALGORITHM", "HS256")
    return secret, algorithm


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    secret, algorithm = _get_jwt_settings()
    try:
        payload = jwt.decode(credentials.credentials, secret, algorithms=[algorithm])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    email = payload.get("email") or payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")

    role_value = str(payload.get("role", UserRole.DEVELOPER.value)).lower()
    if role_value not in {role.value for role in UserRole}:
        raise HTTPException(status_code=401, detail="Invalid token")

    project_ids = payload.get("project_ids") or payload.get("projects") or []
    if not isinstance(project_ids, list):
        raise HTTPException(status_code=401, detail="Invalid token")

    return CurrentUser(
        email=str(email),
        role=UserRole(role_value),
        project_ids={str(project_id) for project_id in project_ids},
    )
