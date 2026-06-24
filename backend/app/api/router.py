from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import projects, ws

router = APIRouter(prefix="/api/v1")

router.include_router(projects.router, prefix="/projects", tags=["Projects"])
router.include_router(ws.router)
