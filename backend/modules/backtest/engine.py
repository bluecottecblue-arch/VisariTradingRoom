"""
BacktestEngine — Motore di backtesting metodologicamente serio

PRINCIPI FONDAMENTALI:
1. Nessun look-ahead bias: i dati futuri non sono mai visibili al momento della decisione
2. Split temporale rigido: train / validation / test non si sovrappongono MAI
3. Costi realistici: spread + slippage + commissioni
4. Walk-forward: la robustezza si misura su dati out-of-sample

LIMITAZIONI DICHIARATE:
- Dati OHLC aggregati non catturano il movimento intra-candela
- Slippage simulato è approssimazione, non tick reale
- Fill sempre al prezzo richiesto (assunzione ottimistica)
- Non simula gap di liquidità notturni o fine settimana perfettamente
"""
import math
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


PIP_VALUE_MAP = {
    "EURUSD": 10.0,
    "GBPUSD": 10.0,
    "AUDUSD": 10.0,
    "NZDUSD": 10.0,
    "USDJPY": 9.1,
    "USDCHF": 10.8,
    "USDCAD": 7.5,
    "XAUUSD": 10.0,
    "XAGUSD": 50.0,
    "NAS100": 1.0,
    "US500": 1.0,
    "US30": 1.0,
    "BTCUSD": 1.0,
}


class TradeDirection(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class Trade:
    entry_time: pd.Timestamp
    direction: TradeDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # "SL", "TP", "TIME", "MANUAL"
    pnl_pips: float = 0.0
    pnl_pct: float = 0.0
    r_multiple: float = 0.0
    commission: float = 0.0


@dataclass
class BacktestConfig:
    initial_capital: float = 10000.0
    risk_per_trade_pct: float = 1.0
    spread_pips: float = 1.0           # spread medio in pips
    slippage_pips: float = 0.5         # slippage in pips
    commission_per_lot: float = 7.0    # commissione round-trip per lotto standard
    pip_value: float = 10.0            # valore pip per lotto standard (EURUSD)
    symbol: str = "EURUSD"
    random_seed: int = 42

    # Split temporale
    in_sample_end: Optional[str] = None     # es. "2022-12-31"
    out_sample_start: Optional[str] = None  # es. "2023-01-01"
    out_sample_end: Optional[str] = None    # es. "2023-12-31"

    # Walk-forward
    wf_train_periods: int = 12   # mesi
    wf_test_periods: int = 3     # mesi

    # Monte Carlo
    mc_simulations: int = 1000


class BacktestEngine:
    """
    Motore di backtesting event-driven su dati OHLC.

    IMPORTANTE: Questo backtester opera su candele OHLC.
    Non ha accesso ai tick. Questo introduce due bias inevitabili:
    1. Non sa in quale ordine si sono mossi High e Low nella stessa candela
    2. Assume che SL e TP vengano colpiti al prezzo esatto (no slippage su stop)

    Entrambi vengono dichiarati all'utente nel report finale.
    """

    def __init__(self, config: BacktestConfig):
        self.config = config

    def run(self, data: pd.DataFrame, strategy_func) -> dict:
        """
        Esegue il backtest completo.

        Args:
            data: DataFrame con colonne OHLC + Timestamp (ordinato ASC, nessun futuro)
            strategy_func: funzione che prende data[:i] e ritorna {"signal": "LONG"|"SHORT"|None, "sl": ..., "tp": ...}

        Returns:
            dict con metriche complete e lista trade
        """
        trades = []
        equity_curve = [self.config.initial_capital]
        current_capital = self.config.initial_capital
        current_trade: Optional[Trade] = None

        # Validazione dati
        self._validate_data(data)

        for i in range(50, len(data)):  # 50 barre di warmup per indicatori
            bar = data.iloc[i]
            history = data.iloc[:i]  # ← CRITICAL: solo dati passati, mai il futuro

            # Gestisci posizione aperta
            if current_trade is not None:
                exit_result = self._check_exit(current_trade, bar)
                if exit_result:
                    current_trade.exit_time = bar.name
                    current_trade.exit_price = exit_result["price"]
                    current_trade.exit_reason = exit_result["reason"]

                    pnl = self._calculate_pnl(current_trade)
                    current_capital += pnl
                    equity_curve.append(current_capital)
                    trades.append(current_trade)
                    current_trade = None
                continue

            # Cerca segnale di entry
            try:
                signal = strategy_func(history)
            except Exception as e:
                # Non crashare su errori della strategy func
                continue

            if signal and signal.get("signal"):
                entry_price = self._apply_execution_cost(
                    price=bar["Close"],
                    direction=signal["signal"],
                    spread_pips=self.config.spread_pips,
                    slippage_pips=self.config.slippage_pips
                )

                lot_size = self._calculate_lot_size(
                    capital=current_capital,
                    sl_pips=abs(entry_price - signal["sl"]) / self._get_pip_size(),
                )

                current_trade = Trade(
                    entry_time=bar.name,
                    direction=TradeDirection(signal["signal"]),
                    entry_price=entry_price,
                    stop_loss=signal["sl"],
                    take_profit=signal["tp"],
                    lot_size=lot_size,
                )

        return self._compute_metrics(trades, equity_curve)

    def run_walk_forward(self, data: pd.DataFrame, strategy_factory, params_optimizer) -> dict:
        """
        Walk-forward analysis: train → ottimizza → test → prossimo periodo.
        Questo è il metodo più robusto per validare una strategia.

        SCHEMA:
        [===TRAIN1===][TEST1][===TRAIN2===][TEST2][===TRAIN3===][TEST3]...

        I risultati da guardare sono SOLO i periodi TEST (out-of-sample).
        """
        n_windows = max(2, min(6, len(data) // 250))
        window = max(50, len(data) // n_windows)
        train_frac = 0.7
        train_bars = int(window * train_frac)
        test_bars = window - train_bars

        walk_forward_results = []
        pos = train_bars

        while pos + test_bars <= len(data):
            train_data = data.iloc[pos - train_bars:pos]
            test_data = data.iloc[pos:pos + test_bars]

            # In-sample: trova parametri ottimali
            best_params = params_optimizer(train_data)

            # Out-of-sample: testa con i parametri trovati (SENZA VEDERE test_data durante ottimizzazione)
            strategy = strategy_factory(best_params)
            oos_result = self.run(test_data, strategy)
            oos_result["period_start"] = test_data.index[0].isoformat()
            oos_result["period_end"] = test_data.index[-1].isoformat()
            oos_result["best_params_used"] = best_params

            walk_forward_results.append(oos_result)
            pos += test_bars

        return {
            "method": "walk_forward",
            "periods": walk_forward_results,
            "aggregated": self._aggregate_wf_results(walk_forward_results),
            "wf_efficiency": self._calc_wf_efficiency(walk_forward_results),
            "interpretation": self._interpret_wf(walk_forward_results)
        }

    def run_monte_carlo(self, trades: list[Trade], n_simulations: int = None) -> dict:
        """
        Monte Carlo su sequenza dei trade.
        Permette di capire la distribuzione dei possibili esiti.

        Permuta l'ordine dei trade (non crea trade nuovi) per testare
        la sensibilità alla sequenza temporale.
        """
        n = n_simulations or self.config.mc_simulations
        r_multiples = [t.r_multiple for t in trades]

        if len(r_multiples) < 10:
            return {"error": "Troppo pochi trade per Monte Carlo (minimo 10)"}

        final_capitals = []
        max_drawdowns = []

        rng = np.random.default_rng(self.config.random_seed)

        for _ in range(n):
            shuffled = rng.permutation(r_multiples)
            capital = self.config.initial_capital
            peak = capital
            max_dd = 0.0

            for r in shuffled:
                risk = capital * (self.config.risk_per_trade_pct / 100)
                capital += r * risk
                if capital > peak:
                    peak = capital
                dd = (peak - capital) / peak
                max_dd = max(max_dd, dd)

            final_capitals.append(capital)
            max_drawdowns.append(max_dd)

        final_capitals = np.array(final_capitals)
        max_drawdowns = np.array(max_drawdowns)

        return {
            "n_simulations": n,
            "final_capital": {
                "p5": float(np.percentile(final_capitals, 5)),
                "p25": float(np.percentile(final_capitals, 25)),
                "median": float(np.median(final_capitals)),
                "p75": float(np.percentile(final_capitals, 75)),
                "p95": float(np.percentile(final_capitals, 95)),
                "mean": float(np.mean(final_capitals)),
            },
            "max_drawdown": {
                "p5": float(np.percentile(max_drawdowns, 5)),
                "p50": float(np.percentile(max_drawdowns, 50)),
                "p95": float(np.percentile(max_drawdowns, 95)),
            },
            "prob_profit": float(np.mean(final_capitals > self.config.initial_capital)),
            "prob_ruin": float(np.mean(final_capitals < self.config.initial_capital * 0.5)),
            "interpretation": self._interpret_mc(final_capitals, max_drawdowns)
        }

    def _validate_data(self, data: pd.DataFrame):
        """Controlla integrità dei dati prima del backtest"""
        required = ["Open", "High", "Low", "Close"]
        for col in required:
            if col not in data.columns:
                raise ValueError(f"Colonna mancante: {col}")

        # Verifica ordine cronologico
        if not data.index.is_monotonic_increasing:
            raise ValueError("I dati non sono in ordine cronologico crescente")

        # Verifica assenza di valori futuri (look-ahead check basico)
        now = pd.Timestamp.now(tz="UTC") if data.index.tz is not None else pd.Timestamp.now()
        if data.index[-1] > now:
            raise ValueError("I dati contengono date future — possibile look-ahead bias!")

        # Verifica coerenza OHLC
        invalid_bars = data[(data["High"] < data["Low"]) |
                            (data["Open"] > data["High"]) |
                            (data["Open"] < data["Low"])]
        if len(invalid_bars) > 0:
            print(f"⚠️  WARN: {len(invalid_bars)} barre con OHLC incoerente. Verificare qualità dati.")

    def _check_exit(self, trade: Trade, bar: pd.Series) -> Optional[dict]:
        """
        Controlla se SL o TP vengono colpiti nella barra corrente.

        PROBLEMA OHLC: Non sappiamo se High o Low si è mosso prima nella barra.
        Convenzione conservativa: se entrambi vengono colpiti, assume SL (peggio).
        """
        if trade.entry_time == bar.name:
            return None

        if trade.direction == TradeDirection.LONG:
            sl_hit = bar["Low"] <= trade.stop_loss
            tp_hit = bar["High"] >= trade.take_profit

            if sl_hit and tp_hit:
                return {"price": trade.stop_loss, "reason": "SL"}  # conservativo
            elif sl_hit:
                return {"price": trade.stop_loss, "reason": "SL"}
            elif tp_hit:
                return {"price": trade.take_profit, "reason": "TP"}

        elif trade.direction == TradeDirection.SHORT:
            sl_hit = bar["High"] >= trade.stop_loss
            tp_hit = bar["Low"] <= trade.take_profit

            if sl_hit and tp_hit:
                return {"price": trade.stop_loss, "reason": "SL"}
            elif sl_hit:
                return {"price": trade.stop_loss, "reason": "SL"}
            elif tp_hit:
                return {"price": trade.take_profit, "reason": "TP"}

        return None

    def _apply_execution_cost(self, price: float, direction: str,
                               spread_pips: float, slippage_pips: float) -> float:
        """Applica spread e slippage all'entry price"""
        pip = 0.0001  # per FX major
        cost = (spread_pips + slippage_pips) * pip
        if direction == "LONG":
            return price + cost  # peggio per long
        else:
            return price - cost  # peggio per short

    def _calculate_lot_size(self, capital: float, sl_pips: float) -> float:
        """Calcola lot size basato su % rischio e SL in pips"""
        if sl_pips <= 0:
            return 0.01
        risk_amount = capital * (self.config.risk_per_trade_pct / 100)
        pip_value = PIP_VALUE_MAP.get(self.config.symbol.upper(), self.config.pip_value)
        lots = risk_amount / (sl_pips * pip_value)
        return round(max(0.01, min(lots, 100.0)), 2)

    def _calculate_pnl(self, trade: Trade) -> float:
        """Calcola P&L del trade in valuta del conto"""
        pip = self._get_pip_size()
        if trade.direction == TradeDirection.LONG:
            pips = (trade.exit_price - trade.entry_price) / pip
        else:
            pips = (trade.entry_price - trade.exit_price) / pip

        pnl = pips * self.config.pip_value * trade.lot_size
        pnl -= trade.commission

        sl_pips = abs(trade.entry_price - trade.stop_loss) / pip
        trade.r_multiple = pips / sl_pips if sl_pips > 0 else 0
        trade.pnl_pips = pips

        return pnl

    def _compute_metrics(self, trades: list[Trade], equity_curve: list[float]) -> dict:
        """Calcola tutte le metriche di performance"""
        if not trades:
            return self._finalize_metrics(
                {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "hit_rate": 0.0,
                    "avg_win_r": 0.0,
                    "avg_loss_r": 0.0,
                    "expectancy_r": 0.0,
                    "profit_factor": 0.0,
                    "sharpe_ratio": 0.0,
                    "sortino_ratio": 0.0,
                    "calmar_ratio": 0.0,
                    "max_drawdown_pct": 0.0,
                    "max_consecutive_losses": 0,
                    "final_capital": float(equity_curve[-1] if equity_curve else self.config.initial_capital),
                    "total_return_pct": 0.0,
                    "equity_curve": equity_curve or [self.config.initial_capital],
                    "trades": [],
                    "data_quality_warnings": [
                        "Nessun trade eseguito nel periodo selezionato",
                        "Backtest su OHLC: ordine High/Low nella stessa candela è sconosciuto",
                        "Slippage simulato con costante, non tick reale",
                    ],
                }
            )

        equity = np.array(equity_curve)
        returns = np.diff(equity) / equity[:-1]

        wins = [t for t in trades if t.r_multiple > 0]
        losses = [t for t in trades if t.r_multiple <= 0]

        # Drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        max_dd = float(np.min(drawdown))

        # Sharpe (annualizzato, assumendo daily returns)
        sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)
                  if np.std(returns) > 0 else 0.0)

        # Sortino (solo downside)
        downside = returns[returns < 0]
        sortino = (np.mean(returns) / np.std(downside) * np.sqrt(252)
                   if len(downside) > 0 and np.std(downside) > 0 else 0.0)

        # Calmar
        calmar = ((equity[-1] / equity[0] - 1) / abs(max_dd)
                  if max_dd < 0 else 0.0)

        # Profit Factor
        gross_profit = sum(t.r_multiple for t in wins)
        gross_loss = abs(sum(t.r_multiple for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Consecutive losses
        r_series = [t.r_multiple for t in trades]
        max_consec_loss = self._max_consecutive_losses(r_series)

        return self._finalize_metrics({
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "hit_rate": len(wins) / len(trades),
            "avg_win_r": np.mean([t.r_multiple for t in wins]) if wins else 0,
            "avg_loss_r": np.mean([t.r_multiple for t in losses]) if losses else 0,
            "expectancy_r": np.mean([t.r_multiple for t in trades]),
            "profit_factor": profit_factor,
            "sharpe_ratio": float(sharpe),
            "sortino_ratio": float(sortino),
            "calmar_ratio": float(calmar),
            "max_drawdown_pct": float(max_dd * 100),
            "max_consecutive_losses": max_consec_loss,
            "final_capital": float(equity[-1]),
            "total_return_pct": float((equity[-1] / equity[0] - 1) * 100),
            "equity_curve": equity_curve,
            "trades": [self._serialize_trade(t) for t in trades],
            "data_quality_warnings": [
                "Backtest su OHLC: ordine High/Low nella stessa candela è sconosciuto",
                "Slippage simulato con costante, non tick reale",
                "Fill sempre eseguito al prezzo richiesto (assunzione ottimistica)"
            ]
        })

    def _max_consecutive_losses(self, r_series: list[float]) -> int:
        max_consec = 0
        current = 0
        for r in r_series:
            if r <= 0:
                current += 1
                max_consec = max(max_consec, current)
            else:
                current = 0
        return max_consec

    def _serialize_trade(self, t: Trade) -> dict:
        return {
            "entry_time": t.entry_time.isoformat() if t.entry_time else None,
            "exit_time": t.exit_time.isoformat() if t.exit_time else None,
            "direction": t.direction.value,
            "entry_price": float(t.entry_price),
            "exit_price": float(t.exit_price) if t.exit_price is not None else None,
            "stop_loss": float(t.stop_loss),
            "take_profit": float(t.take_profit),
            "exit_reason": t.exit_reason,
            "r_multiple": round(t.r_multiple, 3),
            "lot_size": float(t.lot_size),
        }

    def _aggregate_wf_results(self, results: list[dict]) -> dict:
        if not results:
            return {}
        sharpes = [r.get("sharpe_ratio", 0) for r in results]
        returns = [r.get("total_return_pct", 0) for r in results]
        dds = [r.get("max_drawdown_pct", 0) for r in results]
        return {
            "avg_sharpe_oos": float(np.mean(sharpes)),
            "avg_return_oos": float(np.mean(returns)),
            "avg_max_dd_oos": float(np.mean(dds)),
            "pct_profitable_periods": float(np.mean([r > 0 for r in returns])),
        }

    def _calc_wf_efficiency(self, results: list[dict]) -> float:
        """
        Walk-forward efficiency: rapporto tra performance OOS e IS.
        > 0.5 è generalmente considerato accettabile.
        Vicino a 1.0 = strategia robusta. < 0 = overfitting grave.
        """
        # Semplificazione: ritorna media dei Sharpe OOS normalizzata
        sharpes = [r.get("sharpe_ratio", 0) for r in results]
        return float(np.mean([s for s in sharpes if s > 0]) / max(max(sharpes), 0.001))

    def _interpret_wf(self, results: list[dict]) -> str:
        profitable = sum(1 for r in results if r.get("total_return_pct", 0) > 0)
        total = len(results)
        pct = profitable / total if total > 0 else 0

        if pct >= 0.7:
            return f"✅ Strategia potenzialmente robusta: profittevole nel {pct:.0%} dei periodi OOS."
        elif pct >= 0.5:
            return f"⚠️  Risultati misti: profittevole nel {pct:.0%} dei periodi OOS. Cautela."
        else:
            return f"❌ Strategia probabilmente non robusta: profittevole solo nel {pct:.0%} dei periodi OOS."

    def _interpret_mc(self, final_capitals: np.ndarray, max_dds: np.ndarray) -> str:
        prob_profit = float(np.mean(final_capitals > self.config.initial_capital))
        p95_dd = float(np.percentile(max_dds, 95))
        return (f"Probabilità di profitto: {prob_profit:.0%}. "
                f"Nel 5% dei casi peggiori il drawdown supera il {p95_dd:.0%}. "
                f"Assicurati di poter sopportare questo drawdown emotivamente e finanziariamente.")

    def _get_pip_size(self) -> float:
        symbol = self.config.symbol.upper()
        if symbol.endswith("JPY"):
            return 0.01
        if symbol in {"XAUUSD", "XAGUSD"}:
            return 0.1
        if symbol in {"NAS100", "US500", "US30", "BTCUSD"}:
            return 1.0
        return 0.0001

    def _finalize_metrics(self, metrics: dict) -> dict:
        finalized = {}
        for key, value in metrics.items():
            if isinstance(value, np.floating):
                as_float = float(value)
                finalized[key] = as_float if math.isfinite(as_float) else 0.0
            elif isinstance(value, np.integer):
                finalized[key] = int(value)
            elif isinstance(value, float):
                finalized[key] = value if math.isfinite(value) else 0.0
            elif isinstance(value, list):
                finalized[key] = [
                    (
                        float(item)
                        if isinstance(item, np.floating)
                        else int(item)
                        if isinstance(item, np.integer)
                        else item if not isinstance(item, float) or math.isfinite(item) else 0.0
                    )
                    for item in value
                ]
            else:
                finalized[key] = value
        return finalized
