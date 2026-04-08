from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field


class CurrentUser(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    email: str
    writable_projects: set[str] = Field(default_factory=set)

    def can_write(self, project_id: str) -> bool:
        return project_id in self.writable_projects


async def get_current_user() -> CurrentUser:
    raise HTTPException(status_code=401, detail="Authentication required")
