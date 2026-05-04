from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from modules.auth.security import AuthContext, require_authenticated
from modules.projects.store import ProjectStore
from modules.team.store import TeamStore


router = APIRouter()


class CreateTeamRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class UpdateBrandingRequest(BaseModel):
    brand_name: Optional[str] = None
    primary_accent: Optional[str] = None
    support_email: Optional[str] = None
    legal_label: Optional[str] = None
    white_label_enabled: Optional[bool] = None
    settings: Optional[dict[str, Any]] = None


class ReplaceMembersRequest(BaseModel):
    members: list[dict[str, str]] = Field(default_factory=list)


class ShareProjectRequest(BaseModel):
    project_id: str
    team_id: Optional[str] = None


@router.get("/bootstrap")
async def team_bootstrap(context: AuthContext = Depends(require_authenticated)):
    teams = await TeamStore.list_teams_for_user(context.username)
    projects = await ProjectStore.list_projects(context.username)
    return {
        "ok": True,
        "teams": teams,
        "projects": projects,
    }


@router.post("/create")
async def create_team(payload: CreateTeamRequest, context: AuthContext = Depends(require_authenticated)):
    team = await TeamStore.create_team(owner_username=context.username, name=payload.name)
    return {"ok": True, "team": team}


@router.post("/{team_id}/branding")
async def update_branding(
    team_id: str,
    payload: UpdateBrandingRequest,
    context: AuthContext = Depends(require_authenticated),
):
    team = await TeamStore.upsert_branding(owner_username=context.username, team_id=team_id, **payload.model_dump(exclude_none=True))
    if not team:
        raise HTTPException(status_code=404, detail="Team non trovato o non modificabile")
    return {"ok": True, "team": team}


@router.post("/{team_id}/members")
async def replace_members(
    team_id: str,
    payload: ReplaceMembersRequest,
    context: AuthContext = Depends(require_authenticated),
):
    team = await TeamStore.replace_members(owner_username=context.username, team_id=team_id, members=payload.members)
    if not team:
        raise HTTPException(status_code=404, detail="Team non trovato o non modificabile")
    return {"ok": True, "team": team}


@router.post("/share-project")
async def share_project(
    payload: ShareProjectRequest,
    context: AuthContext = Depends(require_authenticated),
):
    assigned = await TeamStore.assign_project_to_team(
        owner_username=context.username,
        project_id=payload.project_id,
        team_id=payload.team_id,
    )
    if not assigned:
        raise HTTPException(status_code=404, detail="Impossibile assegnare il progetto al team")
    return {"ok": True, "project_id": payload.project_id, "team_id": payload.team_id}
