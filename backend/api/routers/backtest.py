"""
Router: Backtest
Gestisce il recupero dati storici, esecuzione backtest, walk-forward, Monte Carlo
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import os
import uuid

from modules.backtest.engine import BacktestEngine, BacktestConfig
from modules.bias.bias_checker import BiasChecker
from modules.data.data_fetcher import DataFetcher

router = APIRouter()
bias_checker = BiasChecker()
_executor = ThreadPoolExecutor(max_workers=2)

# Task status store in-memory (in produzione: Redis o DB)
_task_store: dict = {}
_session_task_map: dict[str, str] = {}


class BacktestRequest(BaseModel):
    session_id: str
    config: dict


@router.post("/run")
async def run_backtest(req: BacktestRequest):
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
    _task_store[task_id] = {"status": "running"}
    _session_task_map[req.session_id] = task_id
    asyncio.create_task(_execute_backtest(task_id, req.model_dump()))
    return {"task_id": task_id, "status": "running"}


def _get_formal_spec_from_session(session_id: str) -> dict:
    """
    In produzione: recupera dal DB.
    Demo: ritorna specifica vuota che genera una strategia placeholder.
    """
    return {
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


def _build_strategy_function(formal_spec: dict, params: dict = None):
    """
    Costruisce una funzione Python che implementa la strategia.
    In produzione: parsing completo della specifica formale.
    Demo: implementa una semplice EMA crossover come placeholder.
    """
    def strategy(history: pd.DataFrame):
        if len(history) < 52:
            return None

        close = history["Close"]
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()

        # ATR per SL
        high = history["High"]
        low = history["Low"]
        tr = pd.DataFrame({
            "hl": high - low,
            "hc": abs(high - close.shift(1)),
            "lc": abs(low - close.shift(1))
        }).max(axis=1)
        atr = tr.ewm(span=14, adjust=False).mean().iloc[-1]

        last_close = close.iloc[-1]
        prev_ema20 = ema20.iloc[-2]
        curr_ema20 = ema20.iloc[-1]
        prev_ema50 = ema50.iloc[-2]
        curr_ema50 = ema50.iloc[-1]

        # Crossover long
        if prev_ema20 <= prev_ema50 and curr_ema20 > curr_ema50:
            sl = last_close - atr * 1.5
            tp = last_close + atr * 3.0
            return {"signal": "LONG", "sl": sl, "tp": tp}

        # Crossover short
        if prev_ema20 >= prev_ema50 and curr_ema20 < curr_ema50:
            sl = last_close + atr * 1.5
            tp = last_close - atr * 3.0
            return {"signal": "SHORT", "sl": sl, "tp": tp}

        return None

    return strategy


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
async def backtest_status(task_id: str):
    """
    Polling dello stato del backtest.
    Il frontend chiama questo endpoint ogni 3 secondi finché status == 'complete' | 'error'.
    """
    result = _task_store.get(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Task non trovato")
    return result


def get_task_for_session(session_id: str) -> Optional[dict]:
    task_id = _session_task_map.get(session_id)
    if not task_id:
        return None
    return {"task_id": task_id, **(_task_store.get(task_id) or {})}


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
        _task_store[task_id] = {"status": "complete", "results": result}
    except Exception as exc:
        _task_store[task_id] = {"status": "error", "error": str(exc)}


def _run_backtest_sync(payload: dict) -> dict:
    cfg = payload["config"]
    session_id = payload["session_id"]
    fetcher = DataFetcher()

    formal_spec = _get_formal_spec_from_session(session_id)
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
    strategy_fn = _build_strategy_function(formal_spec)

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
        wf_results = engine.run_walk_forward(
            data=data,
            strategy_factory=lambda params: _build_strategy_function(formal_spec, params),
            params_optimizer=lambda train_data: {},
        )

    mc_results = None
    if cfg.get("run_monte_carlo", True) and oos_results.get("trades"):
        print("[Backtest] Monte Carlo simulation...")
        trades_obj = _deserialize_trades(oos_results["trades"])
        mc_results = engine.run_monte_carlo(trades_obj, cfg.get("mc_simulations", 1000))

    print("[Backtest] Bias check...")
    bias_results = bias_checker.run_all_checks(
        strategy_spec=formal_spec,
        backtest_config=cfg,
        backtest_results={**oos_results, "walk_forward": wf_results},
        optimization_history=None,
    )

    return {
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
        },
        "in_sample": is_results,
        "out_of_sample": oos_results,
        "walk_forward": wf_results,
        "monte_carlo": mc_results,
        "bias_check": bias_results,
        "methodology_notes": [
            "Le metriche OOS (out-of-sample) sono quelle statisticamente rilevanti",
            "Il bias check rileva automaticamente i problemi metodologici più comuni",
            "I risultati in-sample servono solo come confronto — non per decisioni",
            "Un Sharpe OOS > 1.0 con almeno 100 trade è un buon punto di partenza",
        ],
    }
