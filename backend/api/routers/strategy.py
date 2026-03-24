"""
Router: Strategy
Parse → Resolve Ambiguities → Formalize → Generate Bot
Session state held in module-level singletons (in-memory for local dev).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional
import uuid

from modules.parser.strategy_parser import StrategyParser
from modules.formalizer.formalizer import StrategyFormalizer
from modules.botgen.mql5_generator import MQL5Generator
from modules.common.anthropic_client import estimate_stage_budget, get_usage_summary
from modules.common.strategy_validation import (
    STATUS_INVALID,
    build_bot_result,
    enrich_intake_with_technical_defaults,
    resolve_claude_access,
    validate_strategy_intake,
)
from modules.auth.user_store import get_user_ai_credentials
from modules.research.decision_engine import is_promoted_verdict
from modules.projects.store import ProjectStore
from modules.auth.security import AuthContext, require_authenticated
from db.database import InMemorySessionStore
from api.routers.backtest import get_task_for_session, get_completed_results_for_session

router = APIRouter()

# Module-level singletons — each holds its own in-memory session dict
parser    = StrategyParser()
formalizer = StrategyFormalizer()
bot_gen   = MQL5Generator()


# ─── Request / Response models ────────────────────────────────────────────────

class StrategyIntakeRequest(BaseModel):
    project_id: Optional[str] = None
    name: str
    market: str
    analysis_timeframe: str = "H4"
    execution_timeframe: str = "M15"
    long_entry: str
    short_entry: Optional[str] = None
    invalidation: str
    stop_loss: str
    take_profit: str
    trailing_stop: Optional[str] = None
    risk_per_trade_pct: float = 1.0
    max_daily_trades: int = 3
    trading_hours_start: str = "08:00"
    trading_hours_end: str = "17:00"
    trading_days: list[str] = ["MON", "TUE", "WED", "THU", "FRI"]
    volatility_filter: Optional[str] = None
    trend_filter: Optional[str] = None
    context_filter: Optional[str] = None
    news_management: Optional[str] = None
    spread_management: Optional[str] = None
    manual_exit_rules: Optional[str] = None
    valid_trade_examples: Optional[str] = None
    invalid_trade_examples: Optional[str] = None
    additional_notes: Optional[str] = None
    claude_access: Optional[dict[str, Any]] = None
    macro_news: Optional[dict[str, Any]] = None


class ParseResponse(BaseModel):
    session_id: str
    project_id: Optional[str] = None
    status: str
    validation_status: str
    message: str
    structured_strategy: dict[str, Any] = Field(default_factory=dict)
    ambiguities: list[dict[str, Any]] = Field(default_factory=list)
    required_inputs: list[dict[str, Any]] = Field(default_factory=list)
    codeable_rules: list[dict[str, Any]] = Field(default_factory=list)
    bias_warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    completeness_score: float
    can_proceed: bool = False
    can_generate_code: bool = False
    validation: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)


class PreflightStageEstimate(BaseModel):
    enabled: bool
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    max_tokens: int = 0
    estimated_cost_usd: float = 0.0
    reason: str = ""


class PreflightResponse(BaseModel):
    status: str
    message: str
    blocking_items: int
    completeness_score: float
    ambiguities: list[dict[str, Any]] = Field(default_factory=list)
    required_inputs: list[dict[str, Any]] = Field(default_factory=list)
    validation: dict[str, Any] = Field(default_factory=dict)
    expected_stages: dict[str, PreflightStageEstimate]
    estimated_total_cost_usd: float = 0.0
    next_recommended_action: str


class AmbiguityResolution(BaseModel):
    session_id: str
    resolutions: dict[str, str]


class FormalSpecResponse(BaseModel):
    session_id: str
    project_id: Optional[str] = None
    status: str
    validation_status: str
    message: str
    formal_spec: dict[str, Any] = Field(default_factory=dict)
    state_machine: dict[str, Any] = Field(default_factory=dict)
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    non_optimizable: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    ambiguities: list[dict[str, Any]] = Field(default_factory=list)
    required_inputs: list[dict[str, Any]] = Field(default_factory=list)
    can_generate_code: bool = False
    validation: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)


class BotGenerationResponse(BaseModel):
    session_id: str
    project_id: Optional[str] = None
    status: str
    validation_status: str
    message: str
    mql5_code: str = ""
    documentation: str = ""
    implementation_assumptions: list[str] = Field(default_factory=list)
    limitations_vs_discretionary: list[str] = Field(default_factory=list)
    required_inputs: list[dict[str, Any]] = Field(default_factory=list)
    code_validation: dict[str, Any] = Field(default_factory=dict)
    deployment_readiness: dict[str, Any] = Field(default_factory=dict)
    download_ready: bool = False
    can_generate_code: bool = False
    validation: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)


# ─── Endpoints ────────────────────────────────────────────────────────────────


def _build_preflight_estimates(intake: dict, validation_result: dict) -> dict[str, PreflightStageEstimate]:
    blocking = int((validation_result.get("validation") or {}).get("blocking_issues", 0))
    if blocking > 0 or validation_result.get("status") != "VALID":
        disabled_reason = "Pipeline bloccata dal pre-check locale finché mancano dettagli codificabili."
        return {
            "parse": PreflightStageEstimate(enabled=False, reason=disabled_reason),
            "formalize": PreflightStageEstimate(enabled=False, reason=disabled_reason),
            "botgen": PreflightStageEstimate(enabled=False, reason=disabled_reason),
        }

    parse_budget = estimate_stage_budget("parse", intake, expected_output_ratio=0.22)
    formalize_budget = estimate_stage_budget(
        "formalize",
        {"intake": intake, "parsed": validation_result.get("structured_strategy", {})},
        expected_output_ratio=0.2,
    )
    botgen_budget = estimate_stage_budget(
        "botgen",
        {"intake": intake, "formalization_expected": "formal_spec + state_machine + parameters"},
        expected_output_ratio=0.72,
    )
    return {
        "parse": PreflightStageEstimate(
            enabled=True,
            reason="La strategia è abbastanza specifica per la revisione AI.",
            **parse_budget,
        ),
        "formalize": PreflightStageEstimate(
            enabled=True,
            reason="Formalizzazione disponibile solo dopo parse valida.",
            **formalize_budget,
        ),
        "botgen": PreflightStageEstimate(
            enabled=True,
            reason="Generazione consentita solo dopo formal spec valida e verdict research promosso.",
            **botgen_budget,
        ),
    }


async def _resolve_project(
    *,
    owner_username: str,
    requested_project_id: Optional[str],
    title: str,
    mode: str = "strategy",
) -> dict[str, Any]:
    if requested_project_id:
        project = await ProjectStore.get_project(owner_username, requested_project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Progetto non trovato o non accessibile")
        return project
    return await ProjectStore.create_project(
        owner_username=owner_username,
        title=title or "Untitled Strategy",
        mode=mode,
    )


def _project_ref_for_session(session_id: str) -> dict[str, Any]:
    return InMemorySessionStore.get(session_id, "project_ref") or {}


async def _track_project_version(
    *,
    project_id: Optional[str],
    session_id: str,
    version_kind: str,
    status: str,
    payload: Any,
    summary: Optional[dict[str, Any]] = None,
) -> None:
    if not project_id:
        return
    await ProjectStore.add_version(
        project_id=project_id,
        session_id=session_id,
        version_kind=version_kind,
        status=status,
        payload=payload,
        summary=summary or {},
    )


@router.post("/preflight", response_model=PreflightResponse)
async def strategy_preflight(
    req: StrategyIntakeRequest,
    context: AuthContext = Depends(require_authenticated),
):
    """Controllo locale gratuito: codificabilità e budget stimato prima di spendere token."""
    intake = req.model_dump()
    user_creds = get_user_ai_credentials(context.username)
    intake["claude_access"] = resolve_claude_access(
        intake.get("claude_access"),
        account_api_key=user_creds["api_key"],
        account_provider=user_creds["provider"],
    )
    intake = enrich_intake_with_technical_defaults(intake)
    result = validate_strategy_intake(intake)
    estimates = _build_preflight_estimates(intake, result)
    total_cost = round(
        sum(stage.estimated_cost_usd for stage in estimates.values() if stage.enabled),
        6,
    )
    blocking_items = int((result.get("validation") or {}).get("blocking_issues", 0))
    next_action = (
        "Puoi procedere con la revisione AI."
        if result.get("status") == "VALID"
        else "Completa i dettagli bloccanti prima di spendere token."
    )
    return PreflightResponse(
        status=result.get("status", "INVALID"),
        message=result.get("message", ""),
        blocking_items=blocking_items,
        completeness_score=float(result.get("completeness_score", 0.0)),
        ambiguities=result.get("ambiguities", []),
        required_inputs=result.get("required_inputs", []),
        validation=result.get("validation", {}),
        expected_stages=estimates,
        estimated_total_cost_usd=total_cost,
        next_recommended_action=next_action,
    )


@router.post("/parse", response_model=ParseResponse)
async def parse_strategy(
    req: StrategyIntakeRequest,
    context: AuthContext = Depends(require_authenticated),
):
    """Step 1: parse the strategy with Claude, detect ambiguities."""
    session_id = str(uuid.uuid4())
    parse_job: Optional[dict[str, Any]] = None
    try:
        intake = req.model_dump()
        user_creds = get_user_ai_credentials(context.username)
        intake["claude_access"] = resolve_claude_access(
            intake.get("claude_access"),
            account_api_key=user_creds["api_key"],
            account_provider=user_creds["provider"],
        )
        intake = enrich_intake_with_technical_defaults(intake)
        project = await _resolve_project(
            owner_username=context.username,
            requested_project_id=req.project_id,
            title=req.name,
            mode="strategy",
        )
        project_id = project["project_id"]
        InMemorySessionStore.save(session_id, "project_ref", {"project_id": project_id, "owner_username": context.username})
        await ProjectStore.update_project(
            project_id,
            title=req.name.strip() or project["title"],
            active_session_id=session_id,
            metadata={
                "market": req.market,
                "analysis_timeframe": req.analysis_timeframe,
                "execution_timeframe": req.execution_timeframe,
                "claude_access": {
                    "credential_source": (intake.get("claude_access") or {}).get("credential_source", "personal"),
                    "personal_key_supplied": bool((req.claude_access or {}).get("api_key")),
                    "account_key_available": bool((intake.get("claude_access") or {}).get("api_key"))
                    if (intake.get("claude_access") or {}).get("credential_source") == "account"
                    else False,
                },
                "macro_news": {
                    "enabled": bool((req.macro_news or {}).get("enabled")),
                    "provider": (req.macro_news or {}).get("provider", "none"),
                },
            },
        )
        parse_job = await ProjectStore.create_job(
            project_id=project_id,
            session_id=session_id,
            job_type="strategy_parse",
            payload={"stage": "parse", "strategy_name": req.name, "market": req.market},
            status="running",
        )
        await _track_project_version(
            project_id=project_id,
            session_id=session_id,
            version_kind="intake",
            status="submitted",
            payload=intake,
            summary={"name": req.name, "market": req.market},
        )
        result = await parser.parse(session_id=session_id, intake=intake)
        # Store parsed result so formalizer can read it by session_id
        formalizer.store_parsed(session_id, result, intake)
        InMemorySessionStore.save(session_id, "parsed_bundle", {"parsed": result, "intake": intake})
        await _track_project_version(
            project_id=project_id,
            session_id=session_id,
            version_kind="parse_result",
            status=result.get("status", "INVALID"),
            payload=result,
            summary={
                "validation_status": result.get("validation_status"),
                "completeness_score": result.get("completeness_score"),
                "required_inputs": len(result.get("required_inputs", [])),
                "ambiguities": len(result.get("ambiguities", [])),
            },
        )
        await ProjectStore.update_job(
            parse_job["job_id"],
            status="complete",
            result_summary={
                "status": result.get("status"),
                "validation_status": result.get("validation_status"),
                "required_inputs": len(result.get("required_inputs", [])),
            },
        )
        return ParseResponse(session_id=session_id, project_id=project_id, **result)
    except Exception as e:
        if parse_job:
            await ProjectStore.update_job(parse_job["job_id"], status="error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Errore parsing: {str(e)}")


@router.post("/resolve-ambiguities", response_model=FormalSpecResponse)
async def resolve_ambiguities(
    req: AmbiguityResolution,
    context: AuthContext = Depends(require_authenticated),
):
    """Step 2: user chose how to resolve ambiguities → produce formal spec."""
    formalize_job: Optional[dict[str, Any]] = None
    try:
        project_ref = _project_ref_for_session(req.session_id)
        project_id = project_ref.get("project_id")
        formalize_job = await ProjectStore.create_job(
            project_id=project_id,
            session_id=req.session_id,
            job_type="strategy_formalize",
            payload={"stage": "formalize", "resolution_count": len(req.resolutions)},
            status="running",
        )
        result = await formalizer.formalize(
            session_id=req.session_id,
            resolutions=req.resolutions,
        )
        # Store formal spec so bot_gen can read it by session_id
        if result.get("status") == "VALID":
            parsed_bundle = InMemorySessionStore.get(req.session_id, "parsed_bundle") or {}
            intake = parsed_bundle.get("intake") or {}
            bot_gen.store_formal_spec(req.session_id, result, intake.get("claude_access"))
            InMemorySessionStore.save(req.session_id, "formal_spec_bundle", result)
        await _track_project_version(
            project_id=project_id,
            session_id=req.session_id,
            version_kind="formal_spec",
            status=result.get("status", "INVALID"),
            payload=result,
            summary={
                "validation_status": result.get("validation_status"),
                "parameter_count": len(result.get("parameters", [])),
                "can_generate_code": bool(result.get("can_generate_code")),
            },
        )
        if project_id:
            await ProjectStore.update_project(project_id, active_session_id=req.session_id)
        await ProjectStore.update_job(
            formalize_job["job_id"],
            status="complete",
            result_summary={
                "status": result.get("status"),
                "parameter_count": len(result.get("parameters", [])),
            },
        )
        return FormalSpecResponse(session_id=req.session_id, project_id=project_id, **result)
    except Exception as e:
        if formalize_job:
            await ProjectStore.update_job(formalize_job["job_id"], status="error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Errore formalizzazione: {str(e)}")


@router.post("/generate-bot", response_model=BotGenerationResponse)
async def generate_bot(
    session_id: str,
    context: AuthContext = Depends(require_authenticated),
):
    """Step 3: generate MQL5 Expert Advisor from the formal spec."""
    bot_job: Optional[dict[str, Any]] = None
    try:
        project_ref = _project_ref_for_session(session_id)
        project_id = project_ref.get("project_id")
        backtest_results = get_completed_results_for_session(session_id)
        final_decision = (backtest_results or {}).get("final_decision") or {}
        verdict = final_decision.get("verdict")
        if verdict and not is_promoted_verdict(verdict):
            return BotGenerationResponse(
                session_id=session_id,
                project_id=project_id,
                **build_bot_result(
                    status=STATUS_INVALID,
                    message=(
                        "Generazione bloccata dal research layer: verdict=%s. %s"
                        % (
                            verdict,
                            "; ".join(final_decision.get("blockers") or final_decision.get("reasons") or [])
                            or "Servono più ricerca e validazione prima del codice.",
                        )
                    ),
                    required_inputs=[
                        {
                            "id": "req_research_verdict",
                            "field": "backtest",
                            "label": "Migliora il research verdict prima di generare il bot",
                            "why": "Il bot viene generato solo se il verdict finale è almeno PAPER_TRADE_ONLY.",
                            "example": "Aumenta il campione OOS, riduci il drawdown o migliora la robustezza.",
                            "blocking": True,
                        }
                    ],
                ),
            )
        bot_job = await ProjectStore.create_job(
            project_id=project_id,
            session_id=session_id,
            job_type="bot_generation",
            payload={"stage": "bot_generation"},
            status="running",
        )
        result = await bot_gen.generate(session_id=session_id)
        await _track_project_version(
            project_id=project_id,
            session_id=session_id,
            version_kind="bot_code",
            status=result.get("status", "INVALID"),
            payload={
                "validation_status": result.get("validation_status"),
                "documentation": result.get("documentation"),
                "deployment_readiness": result.get("deployment_readiness"),
                "code_validation": result.get("code_validation"),
            },
            summary={
                "download_ready": bool(result.get("download_ready")),
                "code_valid": bool((result.get("code_validation") or {}).get("is_valid")),
                "deployment_status": (result.get("deployment_readiness") or {}).get("status"),
            },
        )
        await ProjectStore.update_job(
            bot_job["job_id"],
            status="complete",
            result_summary={
                "status": result.get("status"),
                "download_ready": bool(result.get("download_ready")),
            },
        )
        return BotGenerationResponse(session_id=session_id, project_id=project_id, **result)
    except Exception as e:
        if bot_job:
            await ProjectStore.update_job(bot_job["job_id"], status="error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Errore generazione bot: {str(e)}")


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Debug: check session state."""
    parsed_bundle = formalizer._sessions.get(session_id) or {}
    parsed = parsed_bundle.get("parsed")
    spec_bundle = bot_gen._sessions.get(session_id) or {}
    spec = spec_bundle.get("spec")
    project_ref = _project_ref_for_session(session_id)
    return {
        "session_id": session_id,
        "project_id": project_ref.get("project_id"),
        "has_parsed": parsed is not None,
        "has_formal_spec": spec is not None,
        "parse_status": (parsed or {}).get("status"),
        "formal_status": (spec or {}).get("status"),
        "parse_usage": (parsed or {}).get("usage", {}),
        "formal_usage": (spec or {}).get("usage", {}),
        "backtest": get_task_for_session(session_id),
    }


@router.get("/usage")
async def get_usage():
    """Metriche aggregate su token/costo/caching delle chiamate LLM."""
    return get_usage_summary()
