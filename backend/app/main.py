from __future__ import annotations

from fastapi import FastAPI

from backend.app.routes.env import router as env_router

app = FastAPI(title="EnvSync")
app.include_router(env_router)
