from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class EnvVersion(BaseModel):
    """One encrypted snapshot of a .env file."""

    project_id: str
    branch: str
    ciphertext: str
    key_names: list[str]
    pushed_by: str
    pushed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int


class AuditEntry(BaseModel):
    """Immutable log entry for vault activity."""

    user_email: str
    action: str
    project_id: str
    branch: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ip_address: Optional[str] = None
