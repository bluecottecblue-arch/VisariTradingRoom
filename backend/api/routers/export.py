"""
Router: Export
Genera e serve i file scaricabili: EA .mq5, report HTML, report JSON
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from pathlib import Path
import os
import json

from modules.report.generator import ReportGenerator
from modules.common.deployment_bundle import (
    build_deployment_readiness,
    build_export_manifest,
    build_setup_text,
)
from modules.common.strategy_validation import validate_mql5_code
from modules.common.public_errors import build_public_error
from modules.research.decision_engine import is_promoted_verdict
from modules.projects.store import ProjectStore
from modules.auth.security import AuthContext, ensure_session_access, require_authenticated
from api.routers.backtest import get_completed_results_for_session
from db.database import InMemorySessionStore

router = APIRouter()
STORAGE = Path(os.environ.get("STORAGE_PATH", "./storage"))
STORAGE.mkdir(exist_ok=True)
report_gen = ReportGenerator(str(STORAGE))


def _build_manifest_for_session(session_id: str, code: str, file_size_bytes: int) -> dict:
    backtest_results = get_completed_results_for_session(session_id) or {}
    formal_spec_bundle = InMemorySessionStore.get(session_id, "formal_spec_bundle") or {}
    code_validation = validate_mql5_code(code)
    deployment_readiness = build_deployment_readiness(
        code=code,
        spec=formal_spec_bundle,
        code_validation=code_validation,
    )
    return build_export_manifest(
        session_id=session_id,
        code=code,
        file_size_bytes=file_size_bytes,
        backtest_results=backtest_results,
        deployment_readiness=deployment_readiness,
    )


def _project_ref_for_session(session_id: str) -> dict:
    return InMemorySessionStore.get(session_id, "project_ref") or {}


async def _register_artifact(
    *,
    session_id: str,
    artifact_type: str,
    label: str,
    storage_path: Path,
    metadata: dict,
) -> None:
    project_id = _project_ref_for_session(session_id).get("project_id")
    if not project_id:
        return
    await ProjectStore.add_artifact(
        project_id=project_id,
        session_id=session_id,
        artifact_type=artifact_type,
        label=label,
        storage_path=str(storage_path),
        metadata=metadata,
    )


@router.get("/mql5/{session_id}")
async def download_mql5(
    session_id: str,
    context: AuthContext = Depends(require_authenticated),
):
    await ensure_session_access(session_id, context)
    backtest_results = get_completed_results_for_session(session_id)
    final_decision = (backtest_results or {}).get("final_decision") or {}
    verdict = final_decision.get("verdict")
    if verdict and not is_promoted_verdict(verdict):
        raise HTTPException(
            status_code=409,
            detail="Download bloccato: verdict finale %s. %s"
            % (
                verdict,
                "; ".join(final_decision.get("blockers") or final_decision.get("reasons") or [])
                or "La strategia non è stata promossa dal research layer.",
            ),
        )
    file_path = STORAGE / f"{session_id}.mq5"
    if not file_path.exists():
        raise HTTPException(status_code=404,
            detail="File .mq5 non trovato. Genera prima il bot.")
    code = file_path.read_text(encoding="utf-8")
    validation = validate_mql5_code(code)
    if not validation["is_valid"]:
        raise HTTPException(
            status_code=409,
            detail="Il file .mq5 salvato non supera la validazione minima: %s"
            % ", ".join(validation["errors"]),
        )
    return FileResponse(str(file_path), media_type="application/octet-stream",
                        filename=f"VisariTradingRoom_{session_id[:8]}.mq5")


@router.post("/mql5/{session_id}")
async def save_mql5(
    session_id: str,
    payload: dict,
    context: AuthContext = Depends(require_authenticated),
):
    await ensure_session_access(session_id, context)
    backtest_results = get_completed_results_for_session(session_id)
    final_decision = (backtest_results or {}).get("final_decision") or {}
    verdict = final_decision.get("verdict")
    if verdict and not is_promoted_verdict(verdict):
        raise HTTPException(
            status_code=409,
            detail="Export bloccato: verdict finale %s. %s"
            % (
                verdict,
                "; ".join(final_decision.get("blockers") or final_decision.get("reasons") or [])
                or "La strategia non è stata promossa dal research layer.",
            ),
        )
    code = payload.get("mql5_code", "")
    if not code:
        raise HTTPException(status_code=400, detail="Codice MQL5 vuoto")
    validation = validate_mql5_code(code)
    if not validation["is_valid"]:
        raise HTTPException(
            status_code=400,
            detail="Codice MQL5 invalido: %s" % ", ".join(validation["errors"]),
        )
    file_path = STORAGE / f"{session_id}.mq5"
    file_path.write_text(code, encoding="utf-8")
    manifest = _build_manifest_for_session(
        session_id=session_id,
        code=code,
        file_size_bytes=file_path.stat().st_size,
    )
    manifest_path = STORAGE / f"{session_id}_manifest.json"
    setup_path = STORAGE / f"{session_id}_setup.txt"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    setup_path.write_text(build_setup_text(manifest), encoding="utf-8")
    await _register_artifact(
        session_id=session_id,
        artifact_type="mql5_source",
        label=f"VisariTradingRoom_{session_id[:8]}.mq5",
        storage_path=file_path,
        metadata={"size_bytes": file_path.stat().st_size, "download_ready": True},
    )
    await _register_artifact(
        session_id=session_id,
        artifact_type="bundle_manifest",
        label=f"VisariTradingRoom_{session_id[:8]}_manifest.json",
        storage_path=manifest_path,
        metadata={"artifact_count": len(manifest.get("artifact_inventory", []))},
    )
    await _register_artifact(
        session_id=session_id,
        artifact_type="setup_guide",
        label=f"VisariTradingRoom_{session_id[:8]}_setup.txt",
        storage_path=setup_path,
        metadata={"lines": len(build_setup_text(manifest).splitlines())},
    )
    project_id = _project_ref_for_session(session_id).get("project_id")
    if project_id:
        await ProjectStore.add_version(
            project_id=project_id,
            session_id=session_id,
            version_kind="export_package",
            status="ready",
            payload=manifest,
            summary={
                "deployment_status": manifest.get("deployment_readiness", {}).get("status"),
                "artifact_count": len(manifest.get("artifact_inventory", [])),
            },
        )
    return {"saved": True, "download_url": f"/api/export/mql5/{session_id}",
            "filename": f"VisariTradingRoom_{session_id[:8]}.mq5", "size_bytes": len(code),
            "warning": "Codice generato da AI. Testa in demo prima di qualsiasi uso live."}


@router.post("/report/{session_id}")
async def generate_report(
    session_id: str,
    payload: dict,
    context: AuthContext = Depends(require_authenticated),
):
    await ensure_session_access(session_id, context)
    try:
        paths = report_gen.generate(session_id, payload)
        html_path = STORAGE / f"{session_id}_report.html"
        json_path = STORAGE / f"{session_id}_report.json"
        await _register_artifact(
            session_id=session_id,
            artifact_type="report_html",
            label=f"VisariTradingRoom_{session_id[:8]}_report.html",
            storage_path=html_path,
            metadata={"size_bytes": html_path.stat().st_size if html_path.exists() else 0},
        )
        await _register_artifact(
            session_id=session_id,
            artifact_type="report_json",
            label=f"VisariTradingRoom_{session_id[:8]}_report.json",
            storage_path=json_path,
            metadata={"size_bytes": json_path.stat().st_size if json_path.exists() else 0},
        )
        return {"generated": True, "html_url": paths["html_url"]}
    except Exception as e:
        logging.exception("Errore generazione report")
        raise HTTPException(status_code=500, detail=build_public_error("Generazione report", e))


@router.get("/report/{session_id}", response_class=HTMLResponse)
async def get_report_html(
    session_id: str,
    context: AuthContext = Depends(require_authenticated),
):
    await ensure_session_access(session_id, context)
    html_path = STORAGE / f"{session_id}_report.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Report non disponibile. Esegui prima il backtest.")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@router.get("/report/{session_id}/json")
async def get_report_json(
    session_id: str,
    context: AuthContext = Depends(require_authenticated),
):
    await ensure_session_access(session_id, context)
    json_path = STORAGE / f"{session_id}_report.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Dati report non disponibili")
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


@router.get("/bundle/{session_id}")
async def get_bundle_info(
    session_id: str,
    context: AuthContext = Depends(require_authenticated),
):
    await ensure_session_access(session_id, context)
    file_path = STORAGE / f"{session_id}.mq5"
    files = {}
    for key, pattern in [
        ("mql5", f"{session_id}.mq5"),
        ("report_html", f"{session_id}_report.html"),
        ("report_json", f"{session_id}_report.json"),
    ]:
        path = STORAGE / pattern
        files[key] = {"available": path.exists(),
                      "size_bytes": path.stat().st_size if path.exists() else 0}
    manifest = None
    if file_path.exists():
        code = file_path.read_text(encoding="utf-8")
        manifest = _build_manifest_for_session(
            session_id=session_id,
            code=code,
            file_size_bytes=file_path.stat().st_size,
        )
    return {
        "session_id": session_id,
        "files": files,
        "urls": {
            "mql5": f"/api/export/mql5/{session_id}",
            "report_html": f"/api/export/report/{session_id}",
            "report_json": f"/api/export/report/{session_id}/json",
            "bundle_manifest": f"/api/export/bundle/{session_id}/manifest.json",
            "bundle_setup": f"/api/export/bundle/{session_id}/setup.txt",
        },
        "manifest": manifest,
    }


@router.get("/bundle/{session_id}/manifest.json")
async def get_bundle_manifest(
    session_id: str,
    context: AuthContext = Depends(require_authenticated),
):
    await ensure_session_access(session_id, context)
    manifest_path = STORAGE / f"{session_id}_manifest.json"
    if manifest_path.exists():
        return JSONResponse(content=json.loads(manifest_path.read_text(encoding="utf-8")))
    file_path = STORAGE / f"{session_id}.mq5"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Bundle non disponibile: file .mq5 non trovato.")
    code = file_path.read_text(encoding="utf-8")
    manifest = _build_manifest_for_session(
        session_id=session_id,
        code=code,
        file_size_bytes=file_path.stat().st_size,
    )
    return JSONResponse(content=manifest)


@router.get("/bundle/{session_id}/setup.txt", response_class=PlainTextResponse)
async def get_bundle_setup_text(
    session_id: str,
    context: AuthContext = Depends(require_authenticated),
):
    await ensure_session_access(session_id, context)
    setup_path = STORAGE / f"{session_id}_setup.txt"
    if setup_path.exists():
        return PlainTextResponse(
            content=setup_path.read_text(encoding="utf-8"),
            headers={"Content-Disposition": f'attachment; filename="VisariTradingRoom_{session_id[:8]}_setup.txt"'},
        )
    file_path = STORAGE / f"{session_id}.mq5"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Guida setup non disponibile: file .mq5 non trovato.")
    code = file_path.read_text(encoding="utf-8")
    manifest = _build_manifest_for_session(
        session_id=session_id,
        code=code,
        file_size_bytes=file_path.stat().st_size,
    )
    return PlainTextResponse(
        content=build_setup_text(manifest),
        headers={"Content-Disposition": f'attachment; filename="VisariTradingRoom_{session_id[:8]}_setup.txt"'},
    )
