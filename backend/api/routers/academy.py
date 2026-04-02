from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from modules.academy.service import AcademyService
from modules.auth.security import AuthContext, require_authenticated


router = APIRouter()


class AcademyProfileUpdateRequest(BaseModel):
    level_input: Optional[str] = None
    freeform_background: Optional[str] = None


class AcademyLessonViewRequest(BaseModel):
    module_id: str
    lesson_id: str


class AcademyLessonProgressRequest(BaseModel):
    module_id: str
    lesson_id: str
    completed: bool


@router.get("/bootstrap")
async def academy_bootstrap(context: AuthContext = Depends(require_authenticated)):
    payload = await AcademyService.bootstrap(context.username)
    return {"ok": True, **payload}


@router.post("/profile")
async def academy_update_profile(
    payload: AcademyProfileUpdateRequest,
    context: AuthContext = Depends(require_authenticated),
):
    result = await AcademyService.update_profile(
        username=context.username,
        level_input=payload.level_input,
        freeform_background=payload.freeform_background,
    )
    return {"ok": True, **result}


@router.post("/lessons/view")
async def academy_mark_viewed(
    payload: AcademyLessonViewRequest,
    context: AuthContext = Depends(require_authenticated),
):
    result = await AcademyService.mark_lesson_viewed(
        username=context.username,
        module_id=payload.module_id,
        lesson_id=payload.lesson_id,
    )
    return {"ok": True, **result}


@router.post("/lessons/progress")
async def academy_set_progress(
    payload: AcademyLessonProgressRequest,
    context: AuthContext = Depends(require_authenticated),
):
    result = await AcademyService.set_lesson_completed(
        username=context.username,
        module_id=payload.module_id,
        lesson_id=payload.lesson_id,
        completed=payload.completed,
    )
    return {"ok": True, **result}


@router.get("/search")
async def academy_search(
    q: str = Query(default=""),
    context: AuthContext = Depends(require_authenticated),
):
    result = await AcademyService.search(username=context.username, query=q)
    return {"ok": True, **result}
