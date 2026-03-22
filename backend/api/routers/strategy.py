"""
Router: Strategy
Parse → Resolve Ambiguities → Formalize → Generate Bot
Session state held in module-level singletons (in-memory for local dev).
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional
import uuid

from modules.parser.strategy_parser import StrategyParser
from modules.formalizer.formalizer import StrategyFormalizer
from modules.botgen.mql5_generator import MQL5Generator
from modules.common.anthropic_client import get_usage_summary
from api.routers.backtest import get_task_for_session

router = APIRouter()

# Module-level singletons — each holds its own in-memory session dict
parser    = StrategyParser()
formalizer = StrategyFormalizer()
bot_gen   = MQL5Generator()


# ─── Request / Response models ────────────────────────────────────────────────

class StrategyIntakeRequest(BaseModel):
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


class ParseResponse(BaseModel):
    session_id: str
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


class AmbiguityResolution(BaseModel):
    session_id: str
    resolutions: dict[str, str]


class FormalSpecResponse(BaseModel):
    session_id: str
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
    status: str
    validation_status: str
    message: str
    mql5_code: str = ""
    documentation: str = ""
    implementation_assumptions: list[str] = Field(default_factory=list)
    limitations_vs_discretionary: list[str] = Field(default_factory=list)
    required_inputs: list[dict[str, Any]] = Field(default_factory=list)
    code_validation: dict[str, Any] = Field(default_factory=dict)
    download_ready: bool = False
    can_generate_code: bool = False
    validation: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/parse", response_model=ParseResponse)
async def parse_strategy(req: StrategyIntakeRequest):
    """Step 1: parse the strategy with Claude, detect ambiguities."""
    session_id = str(uuid.uuid4())
    try:
        result = await parser.parse(session_id=session_id, intake=req.model_dump())
        # Store parsed result so formalizer can read it by session_id
        formalizer.store_parsed(session_id, result, req.model_dump())
        return ParseResponse(session_id=session_id, **result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore parsing: {str(e)}")


@router.post("/resolve-ambiguities", response_model=FormalSpecResponse)
async def resolve_ambiguities(req: AmbiguityResolution):
    """Step 2: user chose how to resolve ambiguities → produce formal spec."""
    try:
        result = await formalizer.formalize(
            session_id=req.session_id,
            resolutions=req.resolutions,
        )
        # Store formal spec so bot_gen can read it by session_id
        if result.get("status") == "VALID":
            bot_gen.store_formal_spec(req.session_id, result)
        return FormalSpecResponse(session_id=req.session_id, **result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore formalizzazione: {str(e)}")


@router.post("/generate-bot", response_model=BotGenerationResponse)
async def generate_bot(session_id: str):
    """Step 3: generate MQL5 Expert Advisor from the formal spec."""
    try:
        result = await bot_gen.generate(session_id=session_id)
        return BotGenerationResponse(session_id=session_id, **result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore generazione bot: {str(e)}")


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Debug: check session state."""
    parsed_bundle = formalizer._sessions.get(session_id) or {}
    parsed = parsed_bundle.get("parsed")
    spec = bot_gen._sessions.get(session_id)
    return {
        "session_id": session_id,
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
