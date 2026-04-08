from __future__ import annotations

from backend.app.models import AuditEntry
from backend.app.db import db


async def log_action(
    user_email: str,
    action: str,
    project_id: str,
    branch: str,
    ip_address: str | None = None,
) -> None:
    entry = AuditEntry(
        user_email=user_email,
        action=action,
        project_id=project_id,
        branch=branch,
        ip_address=ip_address,
    )
    await db.audits.insert_one(entry.model_dump())
