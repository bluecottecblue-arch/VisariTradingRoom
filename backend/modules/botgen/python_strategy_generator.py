from __future__ import annotations

import json
from typing import Any


def build_python_strategy_code(spec: dict[str, Any], session_id: str) -> str:
    formal_spec = spec.get("formal_spec") or {}
    symbol = formal_spec.get("symbol") or formal_spec.get("market") or "SYMBOL"
    strategy_style = formal_spec.get("strategy_style") or "strategy"
    timeframes = formal_spec.get("timeframes") or {}
    entry_conditions = formal_spec.get("entry_conditions") or {}
    risk_management = formal_spec.get("risk_management") or {}
    assumptions = spec.get("assumptions") or []

    config_payload = {
        "symbol": symbol,
        "style": strategy_style,
        "analysis_timeframe": timeframes.get("trend"),
        "execution_timeframe": timeframes.get("entry"),
        "risk_per_trade_pct": risk_management.get("risk_per_trade_pct", 1.0),
        "max_daily_trades": risk_management.get("max_daily_trades", 3),
        "max_positions": risk_management.get("max_positions", 1),
        "entry_conditions": entry_conditions,
        "invalidation": formal_spec.get("invalidation"),
        "stop_loss": formal_spec.get("stop_loss"),
        "take_profit": formal_spec.get("take_profit"),
        "assumptions": assumptions,
    }

    config_json = json.dumps(config_payload, ensure_ascii=False, indent=2)
    return f'''# Built with Visari Trading Room
"""
Python trading algorithm scaffold
Session: {session_id}
Symbol: {symbol}
Style: {strategy_style}

Questo file e pensato per ricerca quantitativa, validazione statistica e
iterazione su dataset OHLCV. Non sostituisce la supervisione del trader.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

import numpy as np
import pandas as pd


CONFIG: Dict[str, Any] = {config_json}


@dataclass
class StrategyConfig:
    symbol: str = CONFIG["symbol"]
    analysis_timeframe: str = CONFIG.get("analysis_timeframe") or "H4"
    execution_timeframe: str = CONFIG.get("execution_timeframe") or "M15"
    risk_per_trade_pct: float = float(CONFIG.get("risk_per_trade_pct", 1.0))
    max_daily_trades: int = int(CONFIG.get("max_daily_trades", 3))
    max_positions: int = int(CONFIG.get("max_positions", 1))


def load_ohlc(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(col).strip() for col in df.columns]
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.dropna(subset=["timestamp"]).set_index("timestamp")
    elif "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
        df = df.dropna(subset=["date"]).set_index("date")
    else:
        raise ValueError("Dataset senza colonna temporale valida.")
    required = ["Open", "High", "Low", "Close"]
    for column in required:
        if column not in df.columns:
            raise ValueError(f"Colonna {{column}} mancante nel dataset.")
    if "Volume" not in df.columns:
        df["Volume"] = 1.0
    return df.sort_index()


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    frame["ret_1"] = frame["Close"].pct_change(1)
    frame["ret_3"] = frame["Close"].pct_change(3)
    frame["ret_5"] = frame["Close"].pct_change(5)
    frame["ema_20"] = frame["Close"].ewm(span=20, adjust=False).mean()
    frame["ema_50"] = frame["Close"].ewm(span=50, adjust=False).mean()
    frame["trend_gap_20"] = frame["Close"] / frame["ema_20"] - 1
    frame["trend_gap_50"] = frame["Close"] / frame["ema_50"] - 1
    frame["vol_20"] = frame["ret_1"].rolling(20).std()
    frame["zscore_20"] = (frame["Close"] - frame["Close"].rolling(20).mean()) / frame["Close"].rolling(20).std()
    frame["range_pct"] = (frame["High"] - frame["Low"]) / frame["Close"].replace(0, np.nan)
    frame["vol_ratio_20"] = frame["Volume"] / frame["Volume"].rolling(20).mean().replace(0, np.nan)
    return frame


def generate_signals(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    # Segnale istituzionale v1: conserva la struttura della strategia
    long_condition = (
        (data["trend_gap_20"] > 0)
        & (data["trend_gap_50"] > -0.002)
        & (data["zscore_20"].between(-1.0, 1.8))
        & (data["vol_20"] > data["vol_20"].rolling(10).mean())
    )
    short_condition = (
        (data["trend_gap_20"] < 0)
        & (data["trend_gap_50"] < 0.002)
        & (data["zscore_20"].between(-1.8, 1.0))
        & (data["vol_20"] > data["vol_20"].rolling(10).mean())
    )
    data["signal"] = np.where(long_condition, 1, np.where(short_condition, -1, 0))
    return data


def simulate_positions(frame: pd.DataFrame, holding_bars: int = 8) -> pd.DataFrame:
    data = frame.copy()
    data["forward_return"] = data["Close"].shift(-holding_bars) / data["Close"] - 1
    data["strategy_return"] = data["signal"] * data["forward_return"]
    data["equity_curve"] = (1 + data["strategy_return"].fillna(0)).cumprod()
    return data


def performance_summary(frame: pd.DataFrame) -> Dict[str, float]:
    sample = frame["strategy_return"].dropna()
    if sample.empty:
        return {{"trades": 0, "mean_return": 0.0, "sharpe_like": 0.0, "max_drawdown": 0.0}}
    equity = (1 + sample).cumprod()
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    sharpe_like = 0.0
    if sample.std() > 0:
        sharpe_like = float(sample.mean() / sample.std() * np.sqrt(252))
    return {{
        "trades": int((frame["signal"] != 0).sum()),
        "mean_return": float(sample.mean()),
        "sharpe_like": float(sharpe_like),
        "max_drawdown": float(drawdown.min()),
        "total_return": float(equity.iloc[-1] - 1) if len(equity) else 0.0,
    }}


def walk_forward_split(frame: pd.DataFrame, train_ratio: float = 0.6, validation_ratio: float = 0.2) -> Dict[str, Any]:
    data = frame.dropna().copy()
    total = len(data)
    train_end = int(total * train_ratio)
    validation_end = int(total * (train_ratio + validation_ratio))
    return {{
        "train": data.iloc[:train_end],
        "validation": data.iloc[train_end:validation_end],
        "test": data.iloc[validation_end:],
    }}


def run_pipeline(path: str) -> Dict[str, Any]:
    raw = load_ohlc(path)
    featured = build_features(raw)
    signalled = generate_signals(featured)
    simulated = simulate_positions(signalled)
    summary = performance_summary(simulated)
    return {{
        "config": CONFIG,
        "summary": summary,
        "latest_rows": simulated.tail(5).reset_index().to_dict(orient="records"),
    }}


if __name__ == "__main__":
    raise SystemExit(
        "Usa run_pipeline(path_csv) dentro il tuo research workflow o importa questo modulo nel Data Lab."
    )
'''
