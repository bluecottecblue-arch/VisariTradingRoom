"""
Router: Backtest
Gestisce il recupero dati storici, esecuzione backtest, walk-forward, Monte Carlo
"""
from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor
import math
import re
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Tuple
import pandas as pd
import os
import uuid
from datetime import datetime, timezone

from modules.backtest.engine import BacktestEngine, BacktestConfig
from modules.bias.bias_checker import BiasChecker
from modules.data.data_fetcher import DataFetcher
from modules.research.statistical_validation import StatisticalValidationSuite
from modules.research.robustness import RobustnessAnalyzer
from modules.research.regime_analysis import RegimeAnalyzer
from modules.research.risk_engine import RiskReviewEngine
from modules.research.decision_engine import DecisionEngine
from modules.fundamentals.economic_calendar import (
    build_news_windows,
    fetch_calendar_events,
    normalize_macro_news_config,
)
from modules.projects.store import ProjectStore
from modules.auth.security import AuthContext, ensure_session_access, require_authenticated
from modules.common.public_errors import build_public_error
from db.database import InMemorySessionStore

router = APIRouter()
bias_checker = BiasChecker()
statistical_suite = StatisticalValidationSuite()
robustness_analyzer = RobustnessAnalyzer()
regime_analyzer = RegimeAnalyzer()
risk_engine = RiskReviewEngine()
decision_engine = DecisionEngine()
_executor = ThreadPoolExecutor(max_workers=2)

# Task status store in-memory (in produzione: Redis o DB)
_task_store: dict = {}
_session_task_map: dict[str, str] = {}


class BacktestRequest(BaseModel):
    session_id: str
    project_id: Optional[str] = None
    config: dict


@router.post("/run")
async def run_backtest(
    req: BacktestRequest,
    context: AuthContext = Depends(require_authenticated),
):
    """
    Esegue il backtest completo:
    1. Scarica dati storici dal provider scelto
    2. Valida qualità dei dati
    3. Esegue backtest in-sample
    4. Esegue backtest out-of-sample
    5. Walk-forward (opzionale)
    6. Monte Carlo (opzionale)
    7. Bias check
    8. Compila report finale
    """
    task_id = str(uuid.uuid4())
    project_ref = await ensure_session_access(req.session_id, context)
    project_id = req.project_id or project_ref.get("project_id")
    job = await ProjectStore.create_job(
        project_id=project_id,
        session_id=req.session_id,
        job_type="backtest",
        payload={
            "symbol": req.config.get("symbol"),
            "provider": req.config.get("provider"),
            "timeframe": req.config.get("timeframe"),
        },
        status="running",
    )
    InMemorySessionStore.save(
        req.session_id,
        "project_ref",
        {"project_id": project_id, "owner_username": project_ref.get("owner_username") or context.username},
    )
    _task_store[task_id] = {
        "status": "running",
        "project_id": project_id,
        "job_id": job["job_id"],
        "owner_username": context.username,
    }
    _session_task_map[req.session_id] = task_id
    InMemorySessionStore.save(req.session_id, "backtest_task_ref", {"task_id": task_id})
    asyncio.create_task(
        _execute_backtest(
            task_id,
            {
                **req.model_dump(),
                "project_id": project_id,
                "job_id": job["job_id"],
                "owner_username": context.username,
            },
        )
    )
    return {"task_id": task_id, "job_id": job["job_id"], "project_id": project_id, "status": "running"}


def _get_formal_spec_from_session(session_id: str) -> dict:
    """
    Recupera la specifica formale dallo store condiviso.
    Se assente, usa un fallback demo esplicito.
    """
    stored = InMemorySessionStore.get(session_id, "formal_spec_bundle")
    if stored:
        return stored
    return {
        "status": "VALID",
        "formal_spec": {
            "indicators": [
                {"id": "ema20", "type": "EMA", "params": {"period": 20}, "timeframe": "H1"},
                {"id": "ema50", "type": "EMA", "params": {"period": 50}, "timeframe": "H1"},
            ],
            "entry_conditions": {
                "long": {"conditions": [{"mql5_expression": "ema20 > ema50"}], "logic": "AND"},
                "short": {"conditions": [{"mql5_expression": "ema20 < ema50"}], "logic": "AND"},
            },
            "stop_loss": {"type": "atr_multiple", "atr_period": 14, "atr_multiplier": 1.5},
            "take_profit": {"type": "rr_ratio", "rr_ratio": 2.0},
            "risk_management": {"risk_per_trade_pct": 1.0, "max_daily_trades": 3},
        }
    }


def _build_strategy_function(data: pd.DataFrame, formal_spec: dict, params: dict = None, news_windows: Optional[List[dict]] = None):
    """
    Costruisce una funzione Python che implementa la strategia, ottimizzata con pre-calcolo.
    """
    spec = (formal_spec or {}).get("formal_spec", {}) if formal_spec else {}
    indicators = spec.get("indicators") or []
    strategy_style = str(spec.get("strategy_style") or "").strip().lower() or "trend_following"
    macro_news = normalize_macro_news_config(spec.get("macro_news") or spec.get("fundamental_filters"))
    symbol = str((formal_spec or {}).get("symbol") or spec.get("symbol") or "").upper()
    risk_management = spec.get("risk_management") or {}
    news_windows = news_windows or []

    ema_periods = sorted([p for p in _extract_indicator_period(indicators, "EMA") if p])
    fast_ema_p = ema_periods[0] if ema_periods else 20
    slow_ema_p = ema_periods[1] if len(ema_periods) > 1 else 50
    rsi_p = next(iter(_extract_indicator_period(indicators, "RSI")), None) or 14
    atr_p = next(iter(_extract_indicator_period(indicators, "ATR")), None) or 14
    rr_ratio = _safe_float((spec.get("take_profit") or {}).get("rr_ratio"), 2.0)
    atr_multiplier = _safe_float((spec.get("stop_loss") or {}).get("atr_multiplier"), 1.5)
    session_window = _extract_session_window(risk_management)
    directional_bias = str(macro_news.get("directional_bias") or "").strip().lower()
    bias_mode = str(macro_news.get("bias_mode") or "").strip().lower()

    # Pre-calcolo vettoriale degli indicatori (MOLTO più veloce di calcolarli in loop)
    close = data["Close"]
    high = data["High"]
    low = data["Low"]
    
    ema_fast = close.ewm(span=max(2, fast_ema_p), adjust=False).mean()
    ema_slow = close.ewm(span=max(max(3, fast_ema_p + 1), slow_ema_p), adjust=False).mean()
    
    tr = pd.DataFrame({
        "hl": high - low,
        "hc": abs(high - close.shift(1)),
        "lc": abs(low - close.shift(1))
    }).max(axis=1)
    atr = tr.ewm(span=max(2, atr_p), adjust=False).mean()
    rsi = _compute_rsi(close, rsi_p)

    def strategy(history: pd.DataFrame):
        # NOTA: history è data.iloc[:i]. Usiamo l'ultimo indice per accedere ai dati pre-calcolati.
        i = len(history) - 1
        if i < 50: return None

        last_ts = history.index[-1]
        if session_window and not _timestamp_in_session(last_ts, session_window):
            return None
        if news_windows and _is_in_news_blackout(last_ts, news_windows):
            return None

        curr_close = close.iloc[i]
        curr_fast = ema_fast.iloc[i]
        prev_fast = ema_fast.iloc[i-1]
        curr_slow = ema_slow.iloc[i]
        prev_slow = ema_slow.iloc[i-1]
        curr_rsi = rsi.iloc[i]
        curr_atr = atr.iloc[i]

        signal = None
        if strategy_style == "breakout":
            rolling_high = high.iloc[max(0, i-20):i].max()
            rolling_low = low.iloc[max(0, i-20):i].min()
            if curr_close > rolling_high: signal = "LONG"
            elif curr_close < rolling_low: signal = "SHORT"
        elif strategy_style == "mean_reversion":
            if curr_rsi <= 30 and curr_fast >= curr_slow: signal = "LONG"
            elif curr_rsi >= 70 and curr_fast <= curr_slow: signal = "SHORT"
        else:
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                signal = "LONG"
            elif prev_fast >= prev_slow and curr_fast < curr_slow:
                signal = "SHORT"
            elif curr_fast > curr_slow and curr_rsi > 55:
                signal = "LONG"
            elif curr_fast < curr_slow and curr_rsi < 45:
                signal = "SHORT"

        if signal and bias_mode == "confirm_with_bias" and directional_bias:
            if not _bias_allows_signal(signal, symbol, directional_bias):
                return None

        if signal == "LONG":
            return {"signal": "LONG", "sl": curr_close - curr_atr * atr_multiplier, "tp": curr_close + curr_atr * max(1.2, atr_multiplier * rr_ratio)}
        if signal == "SHORT":
            return {"signal": "SHORT", "sl": curr_close + curr_atr * atr_multiplier, "tp": curr_close - curr_atr * max(1.2, atr_multiplier * rr_ratio)}

        return None

    return strategy


def _build_implementation_context(session_id: str, formal_spec_bundle: dict) -> dict:
    stored = InMemorySessionStore.get(session_id, "formal_spec_bundle")
    using_real_spec = bool(stored)
    source = ((formal_spec_bundle or {}).get("formal_spec") or {}).get("source") or ("session_store" if using_real_spec else "demo_fallback")
    adapter = "ema_crossover_proxy"
    completeness = 0.58 if using_real_spec else 0.32
    if source == "uploaded_bot":
        adapter = "uploaded_bot_proxy"
        completeness = 0.67
    return {
        "formal_spec_source": source,
        "strategy_adapter": adapter,
        "completeness": completeness,
        "notes": (
            "Il backtest usa ancora un adapter proxy ricostruito dalla formal spec; i risultati servono per research gating, "
            "non per certificare che l'implementazione originale replichi perfettamente il bot."
        ),
    }


def _make_json_safe(value):
    if isinstance(value, dict):
        return {key: _make_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_make_json_safe(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else 0.0
    return value


def _deserialize_trades(trades_data: list) -> list:
    """Ricostruisce oggetti Trade dai dati serializzati"""
    from modules.backtest.engine import Trade, TradeDirection
    result = []
    for t in trades_data:
        trade = Trade(
            entry_time=pd.Timestamp(t["entry_time"]) if t.get("entry_time") else pd.Timestamp.now(),
            direction=TradeDirection(t.get("direction", "LONG")),
            entry_price=t.get("entry_price", 0),
            stop_loss=t.get("stop_loss", 0),
            take_profit=t.get("take_profit", 0),
            lot_size=t.get("lot_size", 0.01),
            exit_time=pd.Timestamp(t["exit_time"]) if t.get("exit_time") else None,
            exit_price=t.get("exit_price"),
            exit_reason=t.get("exit_reason"),
            r_multiple=t.get("r_multiple", 0),
        )
        result.append(trade)
    return result


@router.get("/status/{task_id}")
async def backtest_status(
    task_id: str,
    context: AuthContext = Depends(require_authenticated),
):
    """
    Polling dello stato del backtest.
    Il frontend chiama questo endpoint ogni 3 secondi finché status == 'complete' | 'error'.
    """
    result = await _ensure_task_access(task_id, context)
    if result is None:
        raise HTTPException(status_code=404, detail="Task non trovato")
    return _task_public_view(task_id, result)


@router.get("/session/{session_id}")
async def backtest_status_for_session(
    session_id: str,
    context: AuthContext = Depends(require_authenticated),
):
    await ensure_session_access(session_id, context)
    task = get_task_for_session(session_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Nessun backtest associato a questa sessione")
    return task


async def _ensure_task_access(task_id: str, context: AuthContext) -> Optional[dict]:
    task = _task_store.get(task_id)
    if task is None:
        return None
    if context.role == "admin":
        return task
    owner_username = str(task.get("owner_username") or "").strip().lower()
    if owner_username and owner_username == context.username:
        return task
    project_id = str(task.get("project_id") or "").strip()
    if project_id:
        project = await ProjectStore.get_project(context.username, project_id)
        if project:
            task["owner_username"] = context.username
            return task
    raise HTTPException(status_code=404, detail="Task non trovato")


def get_task_for_session(session_id: str) -> Optional[dict]:
    task_id = _session_task_map.get(session_id)
    if not task_id:
        stored = InMemorySessionStore.get(session_id, "backtest_task_ref") or {}
        task_id = stored.get("task_id")
    if not task_id:
        return None
    task = _task_store.get(task_id) or {}
    return _task_public_view(task_id, task)


def _task_public_view(task_id: str, task: dict) -> dict:
    return {
        key: value
        for key, value in {"task_id": task_id, **(task or {})}.items()
        if key != "owner_username"
    }


def get_completed_results_for_session(session_id: str) -> Optional[dict]:
    task = get_task_for_session(session_id)
    if not task or task.get("status") != "complete":
        return None
    return task.get("results")


@router.get("/providers")
async def list_providers():
    """Ritorna i provider di dati disponibili con info sulla qualità."""
    return {
        "providers": [
            {
                "id": "demo",
                "name": "Demo (dati sintetici)",
                "available": True,
                "api_key_required": False,
                "quality": "NESSUNA — solo per testare il flusso UI",
                "max_history_years": None,
                "cost": "Gratuito",
                "warning": "I dati demo NON hanno valore analitico. Non usare per decisioni reali."
            },
            {
                "id": "polygon",
                "name": "Polygon.io",
                "available": bool(os.environ.get("POLYGON_API_KEY")),
                "api_key_required": True,
                "quality": "BUONA per H1+, SUFFICIENTE per M15",
                "max_history_years": 10,
                "cost": "Gratuito (2 anni, rate limited) / Starter $29/mese (10 anni)",
                "warning": "Dati OHLC aggregati, non tick. Spread non incluso."
            },
            {
                "id": "dukascopy",
                "name": "Dukascopy CSV (locale)",
                "available": os.path.exists(os.environ.get("DUKASCOPY_PATH", "./data/dukascopy")),
                "api_key_required": False,
                "quality": "ECCELLENTE — tick data FX reali",
                "max_history_years": 15,
                "cost": "Gratuito (download manuale)",
                "warning": "Richiede download manuale da dukascopy.com e configurazione DUKASCOPY_PATH"
            }
        ]
    }


async def _execute_backtest(task_id: str, payload: dict) -> None:
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(_executor, _run_backtest_sync, payload)
        project_id = payload.get("project_id")
        job_id = payload.get("job_id")
        owner_username = payload.get("owner_username")
        _task_store[task_id] = {
            "status": "complete",
            "results": result,
            "project_id": project_id,
            "job_id": job_id,
            "owner_username": owner_username,
        }
        if job_id:
            await ProjectStore.update_job(
                job_id,
                status="complete",
                result_summary={
                    "verdict": ((result.get("final_decision") or {}).get("verdict")),
                    "total_trades": ((result.get("out_of_sample") or {}).get("total_trades")),
                    "return_pct": ((result.get("out_of_sample") or {}).get("total_return_pct")),
                },
            )
        if project_id:
            session_id = payload.get("session_id")
            await ProjectStore.update_project(
                project_id,
                active_session_id=session_id,
                latest_verdict=(result.get("final_decision") or {}).get("verdict"),
                metadata={
                    "latest_symbol": ((result.get("data_info") or {}).get("symbol")),
                    "latest_provider": ((result.get("data_info") or {}).get("provider")),
                    "latest_timeframe": ((result.get("data_info") or {}).get("timeframe")),
                },
            )
            await ProjectStore.add_version(
                project_id=project_id,
                session_id=session_id,
                version_kind="backtest",
                status="complete",
                payload=result,
                summary={
                    "verdict": ((result.get("final_decision") or {}).get("verdict")),
                    "oos_total_trades": ((result.get("out_of_sample") or {}).get("total_trades")),
                    "oos_return_pct": ((result.get("out_of_sample") or {}).get("total_return_pct")),
                    "oos_max_drawdown_pct": ((result.get("out_of_sample") or {}).get("max_drawdown_pct")),
                },
            )
    except Exception as exc:
        project_id = payload.get("project_id")
        job_id = payload.get("job_id")
        owner_username = payload.get("owner_username")
        logging.exception("Errore backtest task")
        _task_store[task_id] = {
            "status": "error",
            "error": build_public_error("Backtest", exc),
            "project_id": project_id,
            "job_id": job_id,
            "owner_username": owner_username,
        }
        if job_id:
            await ProjectStore.update_job(job_id, status="error", error=build_public_error("Backtest", exc))


def _run_backtest_sync(payload: dict) -> dict:
    cfg = payload["config"]
    session_id = payload["session_id"]
    project_id = payload.get("project_id")
    fetcher = DataFetcher()

    formal_spec_bundle = _get_formal_spec_from_session(session_id)
    provider = cfg.get("provider", "demo")
    symbol = cfg.get("symbol", "EURUSD")
    timeframe = cfg.get("timeframe", "H1")
    date_from = cfg.get("date_from", "2020-01-01")
    date_to = cfg.get("date_to", "2024-12-31")

    print(f"[Backtest] Scaricamento dati {symbol} {timeframe} da {date_from} a {date_to}")
    data = asyncio.run(
        fetcher.fetch(
            provider=provider,
            symbol=symbol,
            timeframe=timeframe,
            date_from=date_from,
            date_to=date_to,
        )
    )

    if len(data) < 100:
        raise ValueError(
            f"Dati insufficienti: solo {len(data)} barre scaricate. Verifica symbol, timeframe e date."
        )

    backtest_cfg = BacktestConfig(
        initial_capital=cfg.get("initial_capital", 10000),
        risk_per_trade_pct=cfg.get("risk_per_trade_pct", 1.0),
        spread_pips=cfg.get("spread_pips", 1.0),
        slippage_pips=cfg.get("slippage_pips", 0.5),
        commission_per_lot=cfg.get("commission_per_lot", 7.0),
        symbol=symbol,
        in_sample_end=cfg.get("date_in_sample_end"),
        out_sample_start=cfg.get("date_oos_start"),
        out_sample_end=date_to,
        mc_simulations=cfg.get("mc_simulations", 1000),
        random_seed=cfg.get("random_seed", 42),
    )
    engine = BacktestEngine(backtest_cfg)
    calendar_context = {
        "provider": "none",
        "events_used": 0,
        "warnings": [],
        "windows": [],
    }
    macro_news = normalize_macro_news_config(
        cfg.get("macro_news")
        or cfg.get("fundamental_filters")
        or ((formal_spec_bundle.get("formal_spec") or {}).get("macro_news"))
        or ((formal_spec_bundle.get("formal_spec") or {}).get("fundamental_filters"))
    )
    if macro_news.get("enabled"):
        calendar_result = asyncio.run(
            fetch_calendar_events(
                provider_id=macro_news.get("provider", "none"),
                date_from=date_from,
                date_to=date_to,
                currencies=macro_news.get("currencies") or _infer_currencies_from_symbol(symbol),
                impacts=macro_news.get("impacts") or ["high"],
                manual_events=macro_news.get("manual_events") or [],
                api_key=macro_news.get("api_key") or None,
            )
        )
        news_windows = build_news_windows(
            calendar_result.get("events", []),
            blackout_before_min=int(macro_news.get("pre_event_block_minutes", 30) or 30),
            blackout_after_min=int(macro_news.get("post_event_block_minutes", 30) or 30),
        )
        calendar_context = {
            "provider": calendar_result.get("provider"),
            "events_used": len(calendar_result.get("events", [])),
            "warnings": calendar_result.get("warnings", []),
            "windows": news_windows[:50],
            "mode": macro_news.get("mode"),
        }
        if macro_news.get("mode") == "event_driven":
            calendar_context["warnings"] = list(calendar_context["warnings"]) + [
                "Modalità event-driven nel backtest trattata in modo conservativo: il gating è più affidabile del timing preciso post-evento."
            ]
    else:
        news_windows = []
    formal_spec_bundle["symbol"] = symbol
    strategy_fn = _build_strategy_function(data, formal_spec_bundle, news_windows=news_windows)
    implementation_context = _build_implementation_context(session_id, formal_spec_bundle)

    oos_start = cfg.get("date_oos_start")
    if oos_start:
        is_data = data[data.index < oos_start]
        oos_data = data[data.index >= oos_start]
    else:
        split_idx = int(len(data) * 0.7)
        is_data = data.iloc[:split_idx]
        oos_data = data.iloc[split_idx:]

    print(f"[Backtest] In-sample: {len(is_data)} barre")
    is_results = engine.run(is_data, strategy_fn)

    print(f"[Backtest] Out-of-sample: {len(oos_data)} barre")
    oos_results = engine.run(oos_data, strategy_fn)

    wf_results = None
    if cfg.get("run_walk_forward", True) and len(data) > 500:
        print("[Backtest] Walk-forward analysis...")
        wf_data = data.tail(6000) if len(data) > 6000 else data
        wf_results = engine.run_walk_forward(
            data=wf_data,
            strategy_factory=lambda params: _build_strategy_function(wf_data, formal_spec_bundle, params),
            params_optimizer=lambda train_data: {},
        )

    mc_results = None
    if cfg.get("run_monte_carlo", True) and oos_results.get("trades"):
        print("[Backtest] Monte Carlo simulation...")
        trades_obj = _deserialize_trades(oos_results["trades"])
        mc_results = engine.run_monte_carlo(trades_obj, cfg.get("mc_simulations", 1000))

    regime_results = regime_analyzer.analyze(oos_data, oos_results.get("trades", []))
    oos_results["stability_by_regime"] = regime_results.get("by_regime", [])

    print("[Backtest] Bias check...")
    bias_results = bias_checker.run_all_checks(
        strategy_spec=formal_spec_bundle,
        backtest_config=cfg,
        backtest_results={**oos_results, "walk_forward": wf_results},
        optimization_history=None,
    )

    statistical_results = statistical_suite.evaluate(oos_results)
    robustness_results = robustness_analyzer.evaluate(
        base_config=backtest_cfg,
        oos_data=oos_data,
        strategy_fn=strategy_fn,
        in_sample=is_results,
        out_of_sample=oos_results,
        walk_forward=wf_results,
    )
    risk_results = risk_engine.evaluate(cfg, oos_results, mc_results, statistical_results)
    final_decision = decision_engine.evaluate(
        codifiability_status=formal_spec_bundle.get("status", "VALID"),
        formal_status=formal_spec_bundle.get("status", "VALID"),
        implementation_context=implementation_context,
        in_sample=is_results,
        out_of_sample=oos_results,
        bias_check=bias_results,
        statistical=statistical_results,
        robustness=robustness_results,
        regime=regime_results,
        risk=risk_results,
        data_info={"provider": provider, "symbol": symbol, "timeframe": timeframe},
    )
    governance = {
        "strategy_id": session_id,
        "strategy_version": 1,
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "config_snapshot": cfg,
        "metrics_snapshot": {
            "oos_total_trades": oos_results.get("total_trades"),
            "oos_expectancy_r": oos_results.get("expectancy_r"),
            "oos_sharpe_ratio": oos_results.get("sharpe_ratio"),
            "oos_max_drawdown_pct": oos_results.get("max_drawdown_pct"),
            "verdict": final_decision.get("verdict"),
        },
        "final_verdict": final_decision.get("verdict"),
        "reasons_for_verdict": final_decision.get("reasons", []),
        "audit_trail": {
            "provider": provider,
            "symbol": symbol,
            "timeframe": timeframe,
            "implementation_context": implementation_context,
            "cleaning_stats": fetcher.get_cleaning_stats(),
            "calendar_context": calendar_context,
        },
    }

    result = {
        "session_id": session_id,
        "data_info": {
            "provider": provider,
            "symbol": symbol,
            "timeframe": timeframe,
            "total_bars": len(data),
            "in_sample_bars": len(is_data),
            "out_of_sample_bars": len(oos_data),
            "quality_warnings": fetcher.get_quality_warnings(),
            "cleaning_stats": fetcher.get_cleaning_stats(),
            "calendar_context": calendar_context,
        },
        "in_sample": is_results,
        "out_of_sample": oos_results,
        "walk_forward": wf_results,
        "monte_carlo": mc_results,
        "bias_check": bias_results,
        "statistical_validation": statistical_results,
        "robustness_suite": robustness_results,
        "regime_analysis": regime_results,
        "risk_review": risk_results,
        "final_decision": final_decision,
        "research_governance": governance,
        "methodology_notes": [
            "Le metriche OOS (out-of-sample) restano il riferimento principale.",
            "Il research verdict combina qualità OOS, robustezza, regime, rischio e completezza implementativa.",
            implementation_context["notes"],
            "Se il verdict è REJECT o NEEDS_RESEARCH, la generazione bot viene bloccata prima di spendere altri token.",
            *calendar_context.get("warnings", []),
        ],
    }
    safe_result = _make_json_safe(result)
    InMemorySessionStore.save(session_id, "backtest_results_bundle", safe_result)
    if project_id:
        InMemorySessionStore.save(
            session_id,
            "project_ref",
            {"project_id": project_id, "owner_username": payload.get("owner_username")},
        )
    return safe_result


def _extract_indicator_period(indicators: list[dict], indicator_type: str) -> list[int]:
    periods = []
    for indicator in indicators or []:
        if str(indicator.get("type") or "").upper() != indicator_type.upper():
            continue
        raw = indicator.get("period_ref") or indicator.get("params", {}).get("period")
        match = re.search(r"(\d+)", str(raw or ""))
        if match:
            periods.append(int(match.group(1)))
    return periods


def _safe_float(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _compute_rsi(close: pd.Series, period: int) -> pd.Series:
    period = max(2, int(period))
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False).mean().replace(0, 1e-9)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _extract_session_window(risk_management: dict) -> Optional[Tuple[int, int]]:
    start = risk_management.get("session_start_hour")
    end = risk_management.get("session_end_hour")
    if start is None or end is None:
        sessions = risk_management.get("sessions") or []
        for session in sessions:
            match = re.search(r"(\d{1,2}):?(\d{2})?\s*-\s*(\d{1,2}):?(\d{2})?", str(session))
            if match:
                return int(match.group(1)), int(match.group(3))
        return None
    return int(start), int(end)


def _timestamp_in_session(timestamp: pd.Timestamp, session_window: tuple[int, int]) -> bool:
    start_hour, end_hour = session_window
    hour = timestamp.hour
    if start_hour <= end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour


def _is_in_news_blackout(timestamp: pd.Timestamp, news_windows: list[dict]) -> bool:
    ts = timestamp.to_pydatetime().astimezone(timezone.utc)
    for window in news_windows:
        try:
            start = datetime.fromisoformat(window["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(window["end"].replace("Z", "+00:00"))
        except Exception:
            continue
        if start <= ts <= end:
            return True
    return False


def _infer_currencies_from_symbol(symbol: str) -> list[str]:
    normalized = (symbol or "").upper()
    if len(normalized) >= 6:
        return [normalized[:3], normalized[3:6]]
    return ["USD"]


def _bias_allows_signal(signal: str, symbol: str, directional_bias: str) -> bool:
    symbol = (symbol or "").upper()
    bias = directional_bias.lower()
    if "usd" not in bias:
        return True
    bullish = "bullish" in bias or "positive" in bias
    bearish = "bearish" in bias or "negative" in bias
    if not bullish and not bearish:
        return True
    if symbol.endswith("USD"):
        return (signal == "SHORT" if bullish else signal == "LONG")
    if symbol.startswith("USD"):
        return (signal == "LONG" if bullish else signal == "SHORT")
    return True
