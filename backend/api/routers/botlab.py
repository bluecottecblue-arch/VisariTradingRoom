"""
Router Bot Lab.

Permette:
- upload/paste di bot esistenti
- analisi locale
- modifica via prompt
- fundamentals/news filters opzionali
- sessioni compatibili con la pipeline research già esistente
"""
from __future__ import annotations

from typing import Any, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from db.database import InMemorySessionStore
from modules.auth.security import AuthContext, require_authenticated
from modules.botlab.modifier import BotModifier
from modules.botlab.parser import analyze_bot_code, summarize_bot_diff
from modules.common.strategy_validation import empty_usage
from modules.fundamentals.economic_calendar import fetch_calendar_events, list_calendar_providers
from modules.projects.store import ProjectStore

router = APIRouter()
modifier = BotModifier()


class FundamentalFiltersRequest(BaseModel):
    enabled: bool = False
    provider: str = "none"
    api_key: Optional[str] = None
    currencies: list[str] = Field(default_factory=list)
    impacts: list[str] = Field(default_factory=lambda: ["high"])
    blackout_before_min: int = 30
    blackout_after_min: int = 30
    post_event_wait_min: int = 15
    bias_mode: str = "exclude_only"
    directional_bias: Optional[str] = None
    notes: Optional[str] = None
    manual_events: list[dict[str, Any]] = Field(default_factory=list)


class BotUploadRequest(BaseModel):
    project_id: Optional[str] = None
    filename: str
    content: str
    source_origin: str = "user"
    platform_hint: Optional[str] = None
    action_focus: Optional[str] = None
    fundamental_filters: Optional[FundamentalFiltersRequest] = None


class BotModifyRequest(BaseModel):
    session_id: str
    prompt: str
    claude_access: Optional[dict[str, Any]] = None
    fundamental_filters: Optional[FundamentalFiltersRequest] = None


@router.get("/calendar/providers")
async def calendar_providers():
    return {"providers": list_calendar_providers()}


@router.post("/calendar/preview")
async def calendar_preview(filters: FundamentalFiltersRequest):
    result = await fetch_calendar_events(
        provider_id=filters.provider,
        date_from="2025-01-01",
        date_to="2025-12-31",
        currencies=filters.currencies,
        impacts=filters.impacts,
        manual_events=filters.manual_events,
        api_key=filters.api_key,
    )
    return {
        "provider": result["provider"],
        "available_events": len(result["events"]),
        "events_preview": result["events"][:6],
        "warnings": result["warnings"],
    }

@router.post("/upload")
async def upload_bot(
    req: BotUploadRequest,
    context: AuthContext = Depends(require_authenticated),
):
    try:
        session_id = str(uuid.uuid4())
        fundamental_filters = req.fundamental_filters.model_dump() if req.fundamental_filters else None
        if req.project_id:
            project = await ProjectStore.get_project(context.username, req.project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Progetto Bot Lab non trovato")
        else:
            project = await ProjectStore.create_project(
                owner_username=context.username,
                title=req.filename or "Uploaded Bot",
                mode="botlab",
            )
        project_id = project["project_id"]
        analysis = analyze_bot_code(
            filename=req.filename,
            content=req.content,
            source_origin=req.source_origin,
            platform_hint=req.platform_hint,
            fundamental_filters=fundamental_filters,
        )
        analysis["session_id"] = session_id
        analysis["project_id"] = project_id
        analysis["usage"] = empty_usage("botlab_upload")
        analysis["action_focus"] = req.action_focus or "analyze"
        bundle = {
            "source_origin": req.source_origin,
            "filename": req.filename,
            "content": req.content,
            "analysis": analysis,
            "fundamental_filters": fundamental_filters or {},
            "modified_from_session_id": None,
        }
        InMemorySessionStore.save(session_id, "project_ref", {"project_id": project_id, "owner_username": context.username})
        InMemorySessionStore.save(session_id, "bot_lab_bundle", bundle)
        if analysis.get("formal_spec_bundle", {}).get("status") == "VALID":
            InMemorySessionStore.save(session_id, "formal_spec_bundle", analysis["formal_spec_bundle"])
        await ProjectStore.update_project(
            project_id,
            active_session_id=session_id,
            metadata={
                "filename": req.filename,
                "platform": ((analysis.get("file_info") or {}).get("platform")),
                "source_origin": req.source_origin,
            },
        )
        await ProjectStore.add_version(
            project_id=project_id,
            session_id=session_id,
            version_kind="bot_upload_analysis",
            status=analysis.get("status", "INVALID"),
            payload=analysis,
            summary={
                "backtest_ready": bool(analysis.get("backtest_ready")),
                "health_score": ((analysis.get("health_check") or {}).get("score")),
            },
        )
        return analysis
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Errore upload/analyze bot: {exc}")


@router.post("/modify")
async def modify_bot(req: BotModifyRequest):
    stored = InMemorySessionStore.get(req.session_id, "bot_lab_bundle")
    if not stored:
        raise HTTPException(status_code=404, detail="Sessione Bot Lab non trovata")

    fundamental_filters = req.fundamental_filters.model_dump() if req.fundamental_filters else stored.get("fundamental_filters") or {}
    preflight = modifier.validate_prompt(req.prompt, fundamental_filters)
    if preflight["status"] != "VALID":
        return {
            "status": preflight["status"],
            "message": preflight["message"],
            "ambiguities": preflight["ambiguities"],
            "usage": preflight["usage"],
            "original_session_id": req.session_id,
        }

    original_analysis = dict(stored.get("analysis") or {})
    original_analysis["modification_preflight"] = preflight
    llm_modified = await modifier.modify(
        original_code=stored.get("content", ""),
        original_analysis=original_analysis,
        prompt=req.prompt,
        claude_access=req.claude_access or {},
        fundamental_filters=fundamental_filters,
    )
    if llm_modified["status"] != "VALID":
        return {
            **llm_modified,
            "original_session_id": req.session_id,
        }

    new_session_id = str(uuid.uuid4())
    project_ref = InMemorySessionStore.get(req.session_id, "project_ref") or {}
    project_id = project_ref.get("project_id")
    modified_analysis = analyze_bot_code(
        filename=stored.get("filename", "modified_bot.mq5"),
        content=llm_modified["modified_code"],
        source_origin="visari_botlab",
        platform_hint=((original_analysis.get("file_info") or {}).get("platform")),
        fundamental_filters=fundamental_filters,
    )
    modified_analysis["session_id"] = new_session_id
    modified_analysis["project_id"] = project_id
    modified_analysis["usage"] = llm_modified["usage"]
    compare = summarize_bot_diff(original_analysis, modified_analysis)

    modified_bundle = {
        "source_origin": "visari_botlab",
        "filename": stored.get("filename", "modified_bot.mq5"),
        "content": llm_modified["modified_code"],
        "analysis": modified_analysis,
        "fundamental_filters": fundamental_filters,
        "modified_from_session_id": req.session_id,
        "change_summary": llm_modified["change_summary"],
        "conceptual_diff": llm_modified["conceptual_diff"],
        "implementation_notes": llm_modified["implementation_notes"],
        "assumptions": llm_modified["assumptions"],
        "limitations": llm_modified["limitations"],
        "compare": compare,
    }
    if project_id:
        InMemorySessionStore.save(new_session_id, "project_ref", {"project_id": project_id})
    InMemorySessionStore.save(new_session_id, "bot_lab_bundle", modified_bundle)
    if modified_analysis.get("formal_spec_bundle", {}).get("status") == "VALID":
        InMemorySessionStore.save(new_session_id, "formal_spec_bundle", modified_analysis["formal_spec_bundle"])
    if project_id:
        await ProjectStore.update_project(project_id, active_session_id=new_session_id)
        await ProjectStore.add_version(
            project_id=project_id,
            session_id=new_session_id,
            version_kind="bot_modified",
            status="VALID",
            payload={
                "prompt": req.prompt,
                "change_summary": llm_modified["change_summary"],
                "compare": compare,
            },
            summary={
                "change_count": len(llm_modified["change_summary"]),
                "fundamental_filter_added": bool((compare or {}).get("fundamental_filter_added")),
            },
        )

    return {
        "status": "VALID",
        "message": "Versione modificata pronta per confronto, backtest e export.",
        "original_session_id": req.session_id,
        "session_id": new_session_id,
        "project_id": project_id,
        "change_summary": llm_modified["change_summary"],
        "conceptual_diff": llm_modified["conceptual_diff"],
        "implementation_notes": llm_modified["implementation_notes"],
        "assumptions": llm_modified["assumptions"],
        "limitations": llm_modified["limitations"],
        "modified_code": llm_modified["modified_code"],
        "code_validation": llm_modified["code_validation"],
        "modified_analysis": modified_analysis,
        "compare": compare,
        "usage": llm_modified["usage"],
    }


@router.get("/session/{session_id}")
async def bot_lab_session(session_id: str):
    stored = InMemorySessionStore.get(session_id, "bot_lab_bundle")
    if not stored:
        raise HTTPException(status_code=404, detail="Sessione Bot Lab non trovata")
    project_ref = InMemorySessionStore.get(session_id, "project_ref") or {}
    return {
        "session_id": session_id,
        "project_id": project_ref.get("project_id"),
        **stored,
    }
