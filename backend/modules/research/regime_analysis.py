import math

import numpy as np
import pandas as pd


class RegimeAnalyzer:
    def analyze(self, data: pd.DataFrame, trades: list[dict]) -> dict:
        if data is None or data.empty:
            return {"by_regime": [], "dependence_score": 0.0, "warning": "Dati assenti per analisi regime."}

        frame = data.copy()
        close = frame["Close"].astype(float)
        high = frame["High"].astype(float)
        low = frame["Low"].astype(float)
        ema_fast = close.ewm(span=20, adjust=False).mean()
        ema_slow = close.ewm(span=50, adjust=False).mean()
        tr = pd.concat(
            [
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.ewm(span=14, adjust=False).mean().replace(0, np.nan)
        strength = ((ema_fast - ema_slow).abs() / atr).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        vol = close.pct_change().rolling(20).std().fillna(0.0)
        vol_median = float(vol.median()) if not vol.empty else 0.0

        frame["trend_regime"] = np.where(
            strength >= 0.9,
            "trend_strong",
            np.where(strength >= 0.45, "trend_weak", "sideways"),
        )
        frame["vol_regime"] = np.where(vol >= vol_median, "high_vol", "low_vol")
        frame["combined_regime"] = frame["trend_regime"] + "__" + frame["vol_regime"]

        grouped = {}
        total_r = sum(float(t.get("r_multiple", 0.0)) for t in trades) or 0.0

        for trade in trades:
            entry_time = trade.get("entry_time")
            if not entry_time:
                continue
            timestamp = pd.Timestamp(entry_time)
            matching = frame.index.asof(timestamp)
            if pd.isna(matching):
                continue
            row = frame.loc[matching]
            key = str(row["combined_regime"])
            grouped.setdefault(
                key,
                {
                    "regime": key,
                    "trend_regime": str(row["trend_regime"]),
                    "volatility_regime": str(row["vol_regime"]),
                    "trade_count": 0,
                    "wins": 0,
                    "total_r": 0.0,
                    "equity_r": [],
                },
            )
            r_multiple = float(trade.get("r_multiple", 0.0))
            grouped[key]["trade_count"] += 1
            grouped[key]["wins"] += int(r_multiple > 0)
            grouped[key]["total_r"] += r_multiple
            grouped[key]["equity_r"].append(r_multiple)

        regimes = []
        for key, payload in grouped.items():
            count = payload["trade_count"]
            equity_r = payload["equity_r"]
            running = np.cumsum(equity_r) if equity_r else np.array([])
            peak = np.maximum.accumulate(running) if running.size else np.array([])
            drawdown = running - peak if running.size else np.array([])
            regimes.append(
                {
                    "regime": key,
                    "trend_regime": payload["trend_regime"],
                    "volatility_regime": payload["volatility_regime"],
                    "trade_count": count,
                    "expectancy_r": float(payload["total_r"] / count) if count else 0.0,
                    "win_rate": float(payload["wins"] / count) if count else 0.0,
                    "drawdown_r": float(drawdown.min()) if drawdown.size else 0.0,
                    "contribution_to_total_r_pct": float(payload["total_r"] / total_r * 100.0) if total_r else 0.0,
                }
            )

        regimes.sort(key=lambda item: item["trade_count"], reverse=True)
        positive_regimes = [item for item in regimes if item["expectancy_r"] > 0]
        dependence_score = 0.0
        warning = ""
        if positive_regimes:
            dominance = max(abs(item["contribution_to_total_r_pct"]) for item in positive_regimes)
            dependence_score = float(max(0.0, min(1.0, dominance / 100.0)))
            if len(positive_regimes) == 1 or dominance >= 70:
                warning = "La strategia appare fortemente dipendente da un singolo regime di mercato."
        elif regimes:
            dependence_score = 1.0
            warning = "Nessun regime mostra expectancy positiva: edge non confermato."

        return {
            "by_regime": regimes,
            "dependence_score": dependence_score,
            "warning": warning,
            "market_regime_distribution": self._market_regime_distribution(frame["combined_regime"]),
        }

    def _market_regime_distribution(self, values: pd.Series) -> list[dict]:
        if values.empty:
            return []
        counts = values.value_counts(normalize=True)
        return [
            {
                "regime": str(regime),
                "bar_share": float(share),
            }
            for regime, share in counts.items()
        ]
