"""
Celery Worker — Task asincroni per backtest lunghi

I backtest su dati reali possono richiedere 2-10 minuti.
Celery li esegue in background; il frontend fa polling di /api/backtest/status/{task_id}.

Avvio:
    celery -A tasks.worker worker --loglevel=info --concurrency=2

Nota: se Celery non è installato, il backtest viene eseguito in modo sincrono
      direttamente nell'endpoint FastAPI (accettabile per uso locale).
"""
import os
from db.database import resolve_storage_root

try:
    from celery import Celery
    from celery.utils.log import get_task_logger

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    celery_app = Celery("strategyforge", broker=redis_url, backend=redis_url)
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        result_expires=3600,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )
    logger = get_task_logger(__name__)

    @celery_app.task(bind=True, name="strategyforge.run_backtest")
    def run_backtest_task(self, session_id: str, config: dict):
        """
        Task principale di backtest — eseguito in background da Celery.
        Stessa logica del router sincrono, ma con aggiornamenti di stato intermedi.
        """
        def update(phase: str, pct: int = 0):
            self.update_state(state="PROGRESS", meta={"phase": phase, "pct": pct})
            logger.info(f"[{session_id[:8]}] {phase}")

        try:
            import asyncio
            import pandas as pd
            from modules.data.data_fetcher import DataFetcher
            from modules.backtest.engine import BacktestEngine, BacktestConfig, Trade, TradeDirection
            from modules.bias.bias_checker import BiasChecker
            from modules.report.generator import ReportGenerator

            update("Scaricamento dati storici...", 5)
            fetcher = DataFetcher()
            df = asyncio.run(fetcher.fetch(
                provider=config.get("provider", "demo"),
                symbol=config.get("symbol", "EURUSD"),
                timeframe=config.get("timeframe", "H1"),
                date_from=config.get("date_from", "2018-01-01"),
                date_to=config.get("date_to", "2024-12-31"),
            ))
            quality_warnings = fetcher.get_quality_warnings()

            if len(df) < 100:
                raise ValueError(f"Solo {len(df)} barre — insufficiente per backtest")

            update("Backtest in-sample...", 20)
            cfg = BacktestConfig(
                initial_capital=config.get("initial_capital", 10000),
                risk_per_trade_pct=config.get("risk_per_trade_pct", 1.0),
                spread_pips=config.get("spread_pips", 1.0),
                slippage_pips=config.get("slippage_pips", 0.5),
                commission_per_lot=config.get("commission_per_lot", 7.0),
            )
            engine = BacktestEngine(cfg)

            def ema_strategy(history):
                if len(history) < 55: return None
                c = history["Close"]
                e20 = c.ewm(span=20, adjust=False).mean()
                e50 = c.ewm(span=50, adjust=False).mean()
                tr = pd.concat([
                    history["High"] - history["Low"],
                    (history["High"] - c.shift(1)).abs(),
                    (history["Low"] - c.shift(1)).abs()
                ], axis=1).max(axis=1)
                atr = tr.ewm(span=14, adjust=False).mean().iloc[-1]
                last = c.iloc[-1]
                if e20.iloc[-2] <= e50.iloc[-2] and e20.iloc[-1] > e50.iloc[-1]:
                    return {"signal": "LONG", "sl": last - atr*1.5, "tp": last + atr*3.0}
                if e20.iloc[-2] >= e50.iloc[-2] and e20.iloc[-1] < e50.iloc[-1]:
                    return {"signal": "SHORT", "sl": last + atr*1.5, "tp": last - atr*3.0}
                return None

            oos_start = config.get("date_oos_start")
            is_data = df[df.index < oos_start] if oos_start else df.iloc[:int(len(df)*0.7)]
            oos_data = df[df.index >= oos_start] if oos_start else df.iloc[int(len(df)*0.7):]

            is_results = engine.run(is_data, ema_strategy)
            update("Backtest out-of-sample...", 40)
            oos_results = engine.run(oos_data, ema_strategy)

            wf_results = None
            if config.get("run_walk_forward", True) and len(df) > 1000:
                update("Walk-forward analysis...", 60)
                wf_results = engine.run_walk_forward(
                    data=df,
                    strategy_factory=lambda p: ema_strategy,
                    params_optimizer=lambda d: {},
                )

            mc_results = None
            if config.get("run_monte_carlo", True) and oos_results.get("trades"):
                update("Monte Carlo...", 75)
                trades_obj = [
                    Trade(
                        entry_time=pd.Timestamp(t["entry_time"]),
                        direction=TradeDirection(t["direction"]),
                        entry_price=float(t["entry_price"]),
                        stop_loss=float(t["stop_loss"]),
                        take_profit=float(t["take_profit"]),
                        lot_size=float(t["lot_size"]),
                        r_multiple=float(t.get("r_multiple", 0)),
                    ) for t in oos_results["trades"] if t.get("entry_time")
                ]
                if trades_obj:
                    mc_results = engine.run_monte_carlo(trades_obj, config.get("mc_simulations", 1000))

            update("Bias check...", 88)
            bias_results = BiasChecker().run_all_checks(
                strategy_spec={}, backtest_config=config, backtest_results=oos_results
            )

            update("Report...", 95)
            storage = str(resolve_storage_root())
            os.makedirs(storage, exist_ok=True)
            ReportGenerator(storage).generate(session_id, {
                "in_sample": is_results, "out_of_sample": oos_results,
                "walk_forward": wf_results, "monte_carlo": mc_results,
                "bias_check": bias_results,
            })

            return {
                "status": "complete",
                "session_id": session_id,
                "in_sample": is_results,
                "out_of_sample": oos_results,
                "walk_forward": wf_results,
                "monte_carlo": mc_results,
                "bias_check": bias_results,
                "data_info": {
                    "provider": config.get("provider"),
                    "symbol": config.get("symbol"),
                    "quality_warnings": quality_warnings,
                },
            }

        except Exception as exc:
            logger.error(f"Backtest error [{session_id[:8]}]: {exc}", exc_info=True)
            raise self.retry(exc=exc, max_retries=0)

except ImportError:
    # Celery not installed — define a no-op so the module still imports cleanly
    celery_app = None
    def run_backtest_task(*args, **kwargs):
        raise RuntimeError("Celery not installed. Backtest runs synchronously via the API endpoint.")
