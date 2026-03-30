from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from modules.auth.security import AuthContext, require_authenticated
from modules.projects.store import ProjectStore


router = APIRouter()


class CreateProjectRequest(BaseModel):
    title: str
    mode: str = "strategy"


class UpdateProjectRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    latest_verdict: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


@router.get("")
async def list_projects(context: AuthContext = Depends(require_authenticated)):
    projects = await ProjectStore.list_projects(context.username)
    return {
        "ok": True,
        "projects": projects,
    }


@router.post("")
async def create_project(
    payload: CreateProjectRequest,
    context: AuthContext = Depends(require_authenticated),
):
    project = await ProjectStore.create_project(
        owner_username=context.username,
        title=payload.title,
        mode=payload.mode,
    )
    return {
        "ok": True,
        "project": project,
    }


@router.get("/{project_id}")
async def get_project(project_id: str, context: AuthContext = Depends(require_authenticated)):
    project = await ProjectStore.get_project(context.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return {
        "ok": True,
        "project": project,
    }


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    payload: UpdateProjectRequest,
    context: AuthContext = Depends(require_authenticated),
):
    project = await ProjectStore.get_project(context.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    await ProjectStore.update_project(
        project_id,
        **payload.model_dump(exclude_none=True),
    )
    updated = await ProjectStore.get_project(context.username, project_id)
    return {
        "ok": True,
        "project": updated,
    }


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    context: AuthContext = Depends(require_authenticated),
):
    project = await ProjectStore.get_project(context.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    deleted = await ProjectStore.delete_project(context.username, project_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Impossibile eliminare il progetto")

    return {
        "ok": True,
        "deleted": True,
        "project_id": project_id,
    }
