from __future__ import annotations

import hashlib
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from db.database import InMemorySessionStore
from modules.projects.store import ProjectStore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt_currency(value: float) -> str:
    prefix = "-" if value < 0 else ""
    return f"{prefix}${abs(value):,.0f}"


def _fmt_pct(value: float) -> str:
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:.2f}%"


def _market_session(now: datetime) -> str:
    hour = now.hour
    if 0 <= hour < 7:
        return "Asia"
    if 7 <= hour < 13:
        return "London"
    if 13 <= hour < 21:
        return "New York"
    return "Overnight"


def _compute_drawdown_series(equity: list[float]) -> list[float]:
    peak = None
    series: list[float] = []
    for value in equity:
        peak = value if peak is None else max(peak, value)
        dd = 0.0 if not peak else ((value - peak) / peak) * 100
        series.append(round(dd, 4))
    return series


def _build_line_points(values: list[float], start: datetime, step: timedelta, precision: int = 2) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for index, value in enumerate(values):
        ts = start + step * index
        points.append(
            {
                "timestamp": ts.isoformat(),
                "label": ts.strftime("%d %b"),
                "value": round(float(value), precision),
            }
        )
    return points


def _build_distribution(values: list[float], buckets: int = 9) -> list[dict[str, Any]]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    if math.isclose(low, high):
        return [{"label": f"{low:.2f}", "value": len(values)}]
    width = (high - low) / buckets
    counts = [0 for _ in range(buckets)]
    for value in values:
        index = min(buckets - 1, int((value - low) / width))
        counts[index] += 1
    result: list[dict[str, Any]] = []
    for index, count in enumerate(counts):
        start = low + width * index
        end = start + width
        result.append({"label": f"{start:.1f}..{end:.1f}", "value": count})
    return result


def _normalize_curve(
    values: list[Any],
    *,
    start: datetime,
    step: timedelta,
) -> list[dict[str, Any]]:
    if not values:
        return []
    if isinstance(values[0], dict):
        points: list[dict[str, Any]] = []
        for item in values:
            if not isinstance(item, dict):
                continue
            timestamp = item.get("timestamp")
            label = item.get("label")
            value = item.get("value")
            if not isinstance(value, (int, float)):
                continue
            ts = timestamp or _utc_now().isoformat()
            points.append(
                {
                    "timestamp": ts,
                    "label": label or datetime.fromisoformat(str(ts).replace("Z", "+00:00")).strftime("%d %b"),
                    "value": round(float(value), 2),
                }
            )
        return points
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    return _build_line_points(numeric, start, step)


def _strategy_health_label(score: float) -> str:
    if score >= 0.82:
        return "Institutional quality"
    if score >= 0.68:
        return "Stable research candidate"
    if score >= 0.52:
        return "Needs tighter supervision"
    return "Fragile / experimental"


class DashboardService:
    @classmethod
    async def get_command_center(
        cls,
        *,
        owner_username: str,
        project_id: Optional[str] = None,
        timeframe: str = "30D",
        source: str = "auto",
    ) -> dict[str, Any]:
        projects = await ProjectStore.list_projects(owner_username)
        selected_project = await cls._resolve_project(owner_username, projects, project_id)
        selected_detail = (
            await ProjectStore.get_project(owner_username, selected_project["project_id"])
            if selected_project
            else None
        )
        live_monitor_config = await cls._live_monitor_config(selected_project)

        if source == "demo":
            payload = cls._build_mock_response(
                projects=projects,
                selected_project=selected_project,
                selected_detail=selected_detail,
                timeframe=timeframe,
                forced=True,
            )
            payload["live_monitor"] = live_monitor_config
            return payload

        live_payload = await cls._load_live_monitor_payload(selected_detail)
        if source == "live":
            if live_payload:
                payload = cls._build_live_response(
                    projects=projects,
                    selected_project=selected_project,
                    selected_detail=selected_detail,
                    live_payload=live_payload,
                    timeframe=timeframe,
                )
                payload["live_monitor"] = live_monitor_config
                return payload
            payload = cls._build_mock_response(
                projects=projects,
                selected_project=selected_project,
                selected_detail=selected_detail,
                timeframe=timeframe,
                forced=True,
            )
            payload["live_monitor"] = live_monitor_config
            return payload

        if live_payload and source == "auto":
            payload = cls._build_live_response(
                projects=projects,
                selected_project=selected_project,
                selected_detail=selected_detail,
                live_payload=live_payload,
                timeframe=timeframe,
            )
            payload["live_monitor"] = live_monitor_config
            return payload

        real_payload = await cls._load_real_backtest_payload(selected_detail)
        if real_payload:
            payload = cls._build_real_response(
                projects=projects,
                selected_project=selected_project,
                selected_detail=selected_detail,
                backtest_payload=real_payload,
                timeframe=timeframe,
            )
            payload["live_monitor"] = live_monitor_config
            return payload

        payload = cls._build_mock_response(
            projects=projects,
            selected_project=selected_project,
            selected_detail=selected_detail,
            timeframe=timeframe,
            forced=(source in {"real", "live"}),
        )
        payload["live_monitor"] = live_monitor_config
        return payload

    @classmethod
    async def _resolve_project(
        cls,
        owner_username: str,
        projects: list[dict[str, Any]],
        requested_project_id: Optional[str],
    ) -> Optional[dict[str, Any]]:
        if requested_project_id:
            project = await ProjectStore.get_project(owner_username, requested_project_id)
            if project:
                return project
        return projects[0] if projects else None

    @classmethod
    async def _load_real_backtest_payload(cls, project: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if not project:
            return None
        active_session_id = project.get("active_session_id")
        if active_session_id:
            stored = InMemorySessionStore.get(active_session_id, "backtest_results_bundle")
            if stored:
                return stored
        latest = await ProjectStore.get_latest_version(project["project_id"], version_kind="backtest")
        if latest and latest.get("payload"):
            return latest["payload"]
        return None

    @classmethod
    async def _load_live_monitor_payload(cls, project: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if not project:
            return None
        latest = await ProjectStore.get_latest_version(project["project_id"], version_kind="live_monitor_snapshot")
        if latest and latest.get("payload"):
            return latest["payload"]
        return None

    @classmethod
    async def _live_monitor_config(cls, project: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if not project:
            return None
        token = await ProjectStore.ensure_live_monitor_token(project["project_id"])
        metadata = dict(project.get("metadata") or {})
        return {
            "project_id": project["project_id"],
            "monitor_token": token,
            "ingest_path": "/api/dashboard/live-monitor-ingest",
            "last_ingest_at": metadata.get("last_live_ingest_at"),
            "connected": bool(metadata.get("last_live_ingest_at")),
            "sample_fields": [
                "equity",
                "today_pnl_pct",
                "risk_usage_pct",
                "open_positions",
                "recent_signals",
                "latency_ms",
            ],
        }

    @classmethod
    def _build_real_response(
        cls,
        *,
        projects: list[dict[str, Any]],
        selected_project: Optional[dict[str, Any]],
        selected_detail: Optional[dict[str, Any]],
        backtest_payload: dict[str, Any],
        timeframe: str,
    ) -> dict[str, Any]:
        now = _utc_now()
        oos = dict(backtest_payload.get("out_of_sample") or {})
        risk = dict(backtest_payload.get("risk_review") or {})
        regime = dict(backtest_payload.get("regime_analysis") or {})
        robustness = dict(backtest_payload.get("robustness_suite") or {})
        final_decision = dict(backtest_payload.get("final_decision") or {})
        data_info = dict(backtest_payload.get("data_info") or {})
        calendar_context = dict(data_info.get("calendar_context") or {})
        equity_values = [float(value) for value in (oos.get("equity_curve") or []) if isinstance(value, (int, float))]
        if not equity_values:
            return cls._build_mock_response(
                projects=projects,
                selected_project=selected_project,
                selected_detail=selected_detail,
                timeframe=timeframe,
                forced=True,
            )

        step = timedelta(hours=12 if timeframe in {"7D", "14D"} else 24)
        start = now - step * max(1, len(equity_values) - 1)
        equity_curve = _build_line_points(equity_values, start, step)
        drawdown_curve = _build_line_points(_compute_drawdown_series(equity_values), start, step, precision=3)

        trades = list(oos.get("trades") or [])
        trade_r = [float((trade or {}).get("r_multiple") or 0.0) for trade in trades if isinstance(trade, dict)]
        distribution = _build_distribution(trade_r)
        recent_signals = [
            {
                "id": f"sig-{index}",
                "timestamp": trade.get("entry_time") or trade.get("exit_time") or now.isoformat(),
                "symbol": data_info.get("symbol") or "N/A",
                "side": "BUY" if str(trade.get("direction") or "").upper() == "LONG" else "SELL",
                "status": "EXECUTED",
                "price": float(trade.get("entry_price") or 0.0),
                "reason": trade.get("exit_reason") or "Strategy trigger",
            }
            for index, trade in enumerate(reversed(trades[-8:]), start=1)
            if isinstance(trade, dict)
        ]

        project_title = (selected_project or {}).get("title") or "Backtest Review"
        overall_score = float(final_decision.get("overall_score") or 0.0)
        strategy_health_score = max(0, min(100, round(overall_score * 100)))
        warnings = [
            *((final_decision.get("warnings") or [])[:3]),
            *((risk.get("warnings") or [])[:2]),
            *((calendar_context.get("warnings") or [])[:2]),
        ]
        alerts = [
            {
                "tone": "warning" if "warning" in label.lower() else "info",
                "title": "Operating note",
                "detail": item,
            }
            for label, item in [("warning", warning) for warning in warnings[:4]]
        ]

        project_jobs = (selected_detail or {}).get("jobs") or []
        project_artifacts = (selected_detail or {}).get("artifacts") or []
        running_jobs = len([job for job in project_jobs if job.get("status") in {"queued", "running"}])
        export_ready = any(artifact.get("artifact_type") == "bundle_manifest" for artifact in project_artifacts)

        return {
            "as_of": now.isoformat(),
            "source_mode": "real",
            "operating_mode": "BACKTEST_REVIEW",
            "selected_project_id": (selected_project or {}).get("project_id"),
            "selected_project_title": project_title,
            "available_projects": projects,
            "timeframe": timeframe,
            "header": {
                "bot_label": project_title,
                "status": "BACKTEST REVIEW",
                "status_tone": "neutral",
                "current_time": now.isoformat(),
                "market_session": _market_session(now),
                "connection_status": "Historical data linked",
                "connection_tone": "positive",
                "strategy_health_label": _strategy_health_label(overall_score),
                "strategy_health_score": strategy_health_score,
                "desk_mode": "Review / validation",
                "source_label": "Real backtest payload",
            },
            "kpis": [
                {"id": "equity", "label": "Total Equity", "value": _fmt_currency(float(oos.get("final_capital") or 0.0)), "tone": "neutral", "detail": "Out-of-sample final capital"},
                {"id": "pnl", "label": "Session PnL", "value": _fmt_pct(float(oos.get("total_return_pct") or 0.0)), "tone": "positive" if float(oos.get("total_return_pct") or 0.0) >= 0 else "negative", "detail": "Out-of-sample performance"},
                {"id": "positions", "label": "Open Positions", "value": "0", "tone": "neutral", "detail": "Review mode has no live positions"},
                {"id": "winrate", "label": "Win Rate", "value": _fmt_pct(float(oos.get("hit_rate") or 0.0) * 100), "tone": "neutral", "detail": "Executed trades"},
                {"id": "drawdown", "label": "Max Drawdown", "value": _fmt_pct(float(oos.get("max_drawdown_pct") or 0.0)), "tone": "negative", "detail": "Worst equity compression"},
                {"id": "quality", "label": "Quality Score", "value": f"{strategy_health_score}/100", "tone": "positive" if strategy_health_score >= 70 else "warning", "detail": final_decision.get("confidence_label") or "Research confidence"},
                {"id": "risk", "label": "Risk Usage", "value": _fmt_pct(float((risk.get("metrics") or {}).get("variance_pressure_score") or 0.0) * 100), "tone": "warning", "detail": "Variance pressure proxy"},
                {"id": "cash", "label": "Available Cash", "value": _fmt_currency(float(oos.get("final_capital") or 0.0) * (1 - min(0.85, float((risk.get("metrics") or {}).get("risk_concentration_pct") or 0.0) / 100))), "tone": "neutral", "detail": "Approx. deployable capital"},
            ],
            "charts": {
                "equity_curve": equity_curve,
                "drawdown_curve": drawdown_curve,
                "pnl_distribution": distribution,
                "exposure_map": [
                    {"label": data_info.get("symbol") or "Strategy", "value": max(12.0, min(82.0, float((risk.get("metrics") or {}).get("risk_concentration_pct") or 0.0)))},
                    {"label": "Cash buffer", "value": max(8.0, 100.0 - max(12.0, min(82.0, float((risk.get("metrics") or {}).get("risk_concentration_pct") or 0.0))))},
                ],
            },
            "recent_signals": recent_signals,
            "open_positions": [],
            "risk_panel": {
                "risk_usage_pct": round(float((risk.get("metrics") or {}).get("variance_pressure_score") or 0.0) * 100, 2),
                "var_proxy_pct": round(abs(float((risk.get("metrics") or {}).get("worst_daily_return_pct") or 0.0)), 2),
                "leverage_proxy": round(1 + float((risk.get("metrics") or {}).get("risk_concentration_pct") or 0.0) / 60, 2),
                "exposure_pct": round(float((risk.get("metrics") or {}).get("risk_concentration_pct") or 0.0), 2),
                "daily_loss_used_pct": round(min(100.0, abs(float((risk.get("metrics") or {}).get("worst_daily_return_pct") or 0.0)) / max(0.1, float((risk.get("guards") or {}).get("daily_drawdown_guard_pct") or 5.0)) * 100), 2),
                "kill_switch_status": "ARMED" if float((risk.get("metrics") or {}).get("risk_of_ruin_proxy") or 0.0) > 0.15 else "NOMINAL",
                "warnings": risk.get("warnings") or [],
                "max_drawdown_pct": round(float(oos.get("max_drawdown_pct") or 0.0), 2),
            },
            "market_panel": {
                "regime": ((regime.get("by_regime") or [{}])[0] or {}).get("regime") or "Mixed",
                "volatility": ((regime.get("by_regime") or [{}])[0] or {}).get("volatility_regime") or "Unknown",
                "session": _market_session(now),
                "news_risk_active": bool(calendar_context.get("events_used")),
                "news_provider": calendar_context.get("provider") or "none",
                "news_events": int(calendar_context.get("events_used") or 0),
                "macro_filter_status": "Enabled" if (calendar_context.get("provider") or "none") != "none" else "Inactive",
                "directional_bias": (data_info.get("calendar_context") or {}).get("directional_bias") or "Neutral",
                "warnings": calendar_context.get("warnings") or [],
            },
            "tech_panel": {
                "data_provider": data_info.get("provider") or "unknown",
                "data_feed_status": "Healthy",
                "last_sync": (selected_project or {}).get("updated_at") or now.isoformat(),
                "parser_status": "Validated" if any(version.get("version_kind") == "parse_result" for version in ((selected_detail or {}).get("versions") or [])) else "N/A",
                "engine_status": "Ready",
                "provider_status": "Configured" if (calendar_context.get("provider") or "none") != "none" else "No macro provider",
                "export_status": "Package ready" if export_ready else "No bundle yet",
                "last_run_label": backtest_payload.get("research_governance", {}).get("analysis_timestamp") or now.isoformat(),
                "artifacts_ready": len(project_artifacts),
                "jobs_running": running_jobs,
                "latency_ms": 28,
                "warnings": data_info.get("quality_warnings") or [],
            },
            "insight_boxes": [
                {"label": "Strategy Health", "value": f"{strategy_health_score}/100", "tone": "positive" if strategy_health_score >= 70 else "warning", "detail": _strategy_health_label(overall_score)},
                {"label": "News Risk", "value": "Active" if bool(calendar_context.get("events_used")) else "Inactive", "tone": "warning" if bool(calendar_context.get("events_used")) else "neutral", "detail": f"{int(calendar_context.get('events_used') or 0)} scheduled macro windows"},
                {"label": "Robustness", "value": f"{round(float(robustness.get('robustness_score') or 0.0) * 100)} / 100", "tone": "positive" if float(robustness.get("robustness_score") or 0.0) >= 0.7 else "warning", "detail": robustness.get("summary") or "Stress and degradation profile"},
                {"label": "Safe to run?", "value": "Controlled" if final_decision.get("export_allowed") else "Blocked", "tone": "positive" if final_decision.get("export_allowed") else "negative", "detail": "; ".join((final_decision.get("reasons") or final_decision.get("blockers") or ["Review required"]))},
            ],
            "recent_changes": cls._recent_changes(selected_detail),
            "alerts": alerts,
        }

    @classmethod
    def _build_live_response(
        cls,
        *,
        projects: list[dict[str, Any]],
        selected_project: Optional[dict[str, Any]],
        selected_detail: Optional[dict[str, Any]],
        live_payload: dict[str, Any],
        timeframe: str,
    ) -> dict[str, Any]:
        now = _utc_now()
        project_title = (selected_project or {}).get("title") or live_payload.get("bot_label") or "Live Monitor"
        equity_curve = list(live_payload.get("equity_curve") or [])
        if not equity_curve and isinstance(live_payload.get("equity"), (int, float)):
            base_equity = float(live_payload.get("equity") or 0.0)
            equity_curve = [base_equity * (1 - 0.002 * i) for i in reversed(range(10))] + [base_equity]
        step = timedelta(hours=6 if timeframe == "7D" else 12)
        start = now - step * max(1, len(equity_curve) - 1)
        equity_points = _normalize_curve(equity_curve, start=start, step=step)
        curve_values = [point["value"] for point in equity_points]
        drawdown_points = _build_line_points(_compute_drawdown_series(curve_values), start, step, precision=3)
        open_positions = [
            {
                "id": str(item.get("id") or f"pos-{index}"),
                "symbol": str(item.get("symbol") or "N/A"),
                "side": str(item.get("side") or "LONG"),
                "size": float(item.get("size") or 0.0),
                "entry": float(item.get("entry") or 0.0),
                "pnl": float(item.get("pnl") or 0.0),
                "stop": float(item.get("stop") or 0.0),
                "take_profit": float(item.get("take_profit") or 0.0),
                "status": str(item.get("status") or "OPEN"),
            }
            for index, item in enumerate(live_payload.get("open_positions") or [], start=1)
            if isinstance(item, dict)
        ]
        recent_signals = [
            {
                "id": str(item.get("id") or f"sig-{index}"),
                "timestamp": item.get("timestamp") or now.isoformat(),
                "symbol": str(item.get("symbol") or "N/A"),
                "side": str(item.get("side") or "BUY"),
                "status": str(item.get("status") or "EXECUTED"),
                "price": float(item.get("price") or 0.0),
                "reason": str(item.get("reason") or "Live bridge"),
            }
            for index, item in enumerate(live_payload.get("recent_signals") or [], start=1)
            if isinstance(item, dict)
        ]
        distribution_seed = [float(item.get("pnl") or 0.0) for item in open_positions] or [float(live_payload.get("today_pnl_pct") or 0.0)]
        metadata = dict((selected_project or {}).get("metadata") or {})

        return {
            "as_of": live_payload.get("timestamp") or now.isoformat(),
            "source_mode": "live",
            "operating_mode": "LIVE",
            "selected_project_id": (selected_project or {}).get("project_id"),
            "selected_project_title": project_title,
            "available_projects": projects,
            "timeframe": timeframe,
            "header": {
                "bot_label": live_payload.get("bot_label") or project_title,
                "status": "LIVE MONITOR",
                "status_tone": "positive",
                "current_time": live_payload.get("timestamp") or now.isoformat(),
                "market_session": _market_session(now),
                "connection_status": "Live bridge connected",
                "connection_tone": "positive",
                "strategy_health_label": "Live telemetry active",
                "strategy_health_score": max(0, min(100, round(100 - float(live_payload.get("max_drawdown_pct") or 0.0) * 3))),
                "desk_mode": "Live supervision",
                "source_label": "Live project telemetry",
            },
            "kpis": [
                {"id": "equity", "label": "Total Equity", "value": _fmt_currency(float(live_payload.get("equity") or 0.0)), "tone": "neutral", "detail": "Current account equity"},
                {"id": "pnl", "label": "Today PnL", "value": _fmt_pct(float(live_payload.get("today_pnl_pct") or 0.0)), "tone": "positive" if float(live_payload.get("today_pnl_pct") or 0.0) >= 0 else "negative", "detail": "Current live day"},
                {"id": "positions", "label": "Open Positions", "value": str(len(open_positions)), "tone": "neutral", "detail": "Active live tickets"},
                {"id": "winrate", "label": "Feed Status", "value": str(live_payload.get("data_feed_status") or "Live"), "tone": "positive", "detail": "Runtime data feed"},
                {"id": "drawdown", "label": "Max Drawdown", "value": _fmt_pct(float(live_payload.get("max_drawdown_pct") or 0.0)), "tone": "negative", "detail": "Live drawdown"},
                {"id": "quality", "label": "Latency", "value": f"{int(live_payload.get('latency_ms') or 0)} ms", "tone": "neutral", "detail": "Bridge latency"},
                {"id": "risk", "label": "Risk Usage", "value": _fmt_pct(float(live_payload.get("risk_usage_pct") or 0.0)), "tone": "warning", "detail": "Current risk budget"},
                {"id": "cash", "label": "Available Cash", "value": _fmt_currency(float(live_payload.get("available_cash") or live_payload.get("balance") or 0.0)), "tone": "neutral", "detail": "Free live capital"},
            ],
            "charts": {
                "equity_curve": equity_points,
                "drawdown_curve": drawdown_points,
                "pnl_distribution": _build_distribution(distribution_seed),
                "exposure_map": [
                    {"label": "Live exposure", "value": round(float(live_payload.get("exposure_pct") or 0.0), 2)},
                    {"label": "Cash buffer", "value": round(max(0.0, 100.0 - float(live_payload.get("exposure_pct") or 0.0)), 2)},
                ],
            },
            "recent_signals": recent_signals,
            "open_positions": open_positions,
            "risk_panel": {
                "risk_usage_pct": round(float(live_payload.get("risk_usage_pct") or 0.0), 2),
                "var_proxy_pct": round(float(live_payload.get("var_proxy_pct") or 0.0), 2),
                "leverage_proxy": round(float(live_payload.get("leverage_proxy") or 1.0), 2),
                "exposure_pct": round(float(live_payload.get("exposure_pct") or 0.0), 2),
                "daily_loss_used_pct": round(float(live_payload.get("daily_loss_used_pct") or 0.0), 2),
                "kill_switch_status": str(live_payload.get("kill_switch_status") or "NOMINAL"),
                "warnings": list(live_payload.get("warnings") or []),
                "max_drawdown_pct": round(float(live_payload.get("max_drawdown_pct") or 0.0), 2),
            },
            "market_panel": {
                "regime": str(live_payload.get("regime") or "Unknown"),
                "volatility": str(live_payload.get("volatility") or "Unknown"),
                "session": _market_session(now),
                "news_risk_active": bool(live_payload.get("news_risk_active")),
                "news_provider": str(live_payload.get("news_provider") or "none"),
                "news_events": int(live_payload.get("news_events") or 0),
                "macro_filter_status": str(live_payload.get("macro_filter_status") or "Inactive"),
                "directional_bias": str(live_payload.get("directional_bias") or "Neutral"),
                "warnings": list(live_payload.get("warnings") or [])[:3],
            },
            "tech_panel": {
                "data_provider": str(live_payload.get("data_provider") or "mt5_bridge"),
                "data_feed_status": str(live_payload.get("data_feed_status") or "Live"),
                "last_sync": live_payload.get("timestamp") or metadata.get("last_live_ingest_at") or now.isoformat(),
                "parser_status": "N/A",
                "engine_status": str(live_payload.get("engine_status") or "Running"),
                "provider_status": str(live_payload.get("provider_status") or "Connected"),
                "export_status": str(live_payload.get("export_status") or "Package ready"),
                "last_run_label": live_payload.get("timestamp") or now.isoformat(),
                "artifacts_ready": len((selected_detail or {}).get("artifacts") or []),
                "jobs_running": len([job for job in ((selected_detail or {}).get("jobs") or []) if job.get("status") in {"queued", "running"}]),
                "latency_ms": int(live_payload.get("latency_ms") or 0),
                "warnings": list(live_payload.get("warnings") or []),
            },
            "insight_boxes": [
                {"label": "Live Feed", "value": "Connected", "tone": "positive", "detail": "Runtime telemetry linked to the project"},
                {"label": "Drift Risk", "value": "Watch" if float(live_payload.get("max_drawdown_pct") or 0.0) >= 8 else "Contained", "tone": "warning" if float(live_payload.get("max_drawdown_pct") or 0.0) >= 8 else "positive", "detail": "Compare live behavior vs validated profile"},
                {"label": "Macro State", "value": "Armed" if bool(live_payload.get("news_risk_active")) else "Inactive", "tone": "warning" if bool(live_payload.get("news_risk_active")) else "neutral", "detail": "Live macro window supervision"},
                {"label": "Safe to run?", "value": "Controlled" if str(live_payload.get("kill_switch_status") or "NOMINAL") == "NOMINAL" else "Restricted", "tone": "positive" if str(live_payload.get("kill_switch_status") or "NOMINAL") == "NOMINAL" else "negative", "detail": "Live governance status"},
            ],
            "recent_changes": cls._recent_changes(selected_detail) or ["Live monitor linked to current project."],
            "alerts": [
                {
                    "tone": "warning" if float(live_payload.get("daily_loss_used_pct") or 0.0) >= 70 else "neutral",
                    "title": "Live supervision active",
                    "detail": "The desk is now reading live telemetry snapshots instead of review-only payloads.",
                }
            ],
            "live_monitor": {
                "project_id": (selected_project or {}).get("project_id"),
                "monitor_token": metadata.get("live_monitor_token"),
                "ingest_path": "/api/dashboard/live-monitor-ingest",
                "last_ingest_at": metadata.get("last_live_ingest_at") or live_payload.get("timestamp"),
                "connected": True,
                "sample_fields": ["equity", "today_pnl_pct", "risk_usage_pct", "open_positions", "recent_signals", "latency_ms"],
            },
        }

    @classmethod
    def _build_mock_response(
        cls,
        *,
        projects: list[dict[str, Any]],
        selected_project: Optional[dict[str, Any]],
        selected_detail: Optional[dict[str, Any]],
        timeframe: str,
        forced: bool,
    ) -> dict[str, Any]:
        now = _utc_now()
        seed_source = (selected_project or {}).get("project_id") or (selected_project or {}).get("title") or "control-room-demo"
        seed = int(hashlib.sha256(str(seed_source).encode("utf-8")).hexdigest()[:8], 16)
        rng = random.Random(seed)

        point_count = 48 if timeframe == "7D" else 72 if timeframe == "30D" else 96
        base = 100000 + rng.randint(-6000, 6000)
        equity_values: list[float] = []
        current = float(base)
        for index in range(point_count):
            drift = rng.uniform(-0.009, 0.015)
            if index and index % 17 == 0:
                drift -= rng.uniform(0.01, 0.024)
            current *= 1 + drift
            equity_values.append(current)
        step = timedelta(hours=6 if timeframe == "7D" else 12)
        start = now - step * max(1, point_count - 1)
        drawdown_values = _compute_drawdown_series(equity_values)
        trade_r = [rng.gauss(0.18, 0.75) for _ in range(120)]
        exposure_core = rng.uniform(22, 58)
        current_project_title = (selected_project or {}).get("title") or "Global Macro Trend"
        operating_mode = "PAPER" if selected_project else "DEMO"
        strategy_health_score = rng.randint(64, 88)
        alerts = []
        if forced:
            alerts.append(
                {
                    "tone": "warning",
                    "title": "Real data unavailable",
                    "detail": "The command center is showing a professional mock feed because no completed backtest payload is linked to the selected project yet.",
                }
            )
        if min(drawdown_values) < -8:
            alerts.append(
                {
                    "tone": "warning",
                    "title": "Drawdown watch",
                    "detail": "Simulated equity compression breached the internal watch band. Kill-switch remains nominal.",
                }
            )

        return {
            "as_of": now.isoformat(),
            "source_mode": "mock",
            "operating_mode": operating_mode,
            "selected_project_id": (selected_project or {}).get("project_id"),
            "selected_project_title": current_project_title,
            "available_projects": projects,
            "timeframe": timeframe,
            "header": {
                "bot_label": current_project_title,
                "status": "PAPER DESK" if selected_project else "DEMO DESK",
                "status_tone": "positive" if selected_project else "warning",
                "current_time": now.isoformat(),
                "market_session": _market_session(now),
                "connection_status": "Mock telemetry bridge",
                "connection_tone": "warning",
                "strategy_health_label": _strategy_health_label(strategy_health_score / 100),
                "strategy_health_score": strategy_health_score,
                "desk_mode": "Control room preview",
                "source_label": "Professional demo feed",
            },
            "kpis": [
                {"id": "equity", "label": "Total Equity", "value": _fmt_currency(equity_values[-1]), "tone": "neutral", "detail": "Simulated account equity"},
                {"id": "pnl", "label": "Today PnL", "value": _fmt_pct(((equity_values[-1] / equity_values[-5]) - 1) * 100), "tone": "positive" if equity_values[-1] >= equity_values[-5] else "negative", "detail": "Latest desk move"},
                {"id": "positions", "label": "Open Positions", "value": str(rng.randint(1, 4)), "tone": "neutral", "detail": "Simulated active tickets"},
                {"id": "winrate", "label": "Win Rate", "value": _fmt_pct(rng.uniform(48, 66)), "tone": "neutral", "detail": "Rolling hit rate"},
                {"id": "drawdown", "label": "Max Drawdown", "value": _fmt_pct(min(drawdown_values)), "tone": "negative", "detail": "Simulated peak-to-trough"},
                {"id": "quality", "label": "Quality Score", "value": f"{strategy_health_score}/100", "tone": "positive" if strategy_health_score >= 75 else "warning", "detail": "Health composite"},
                {"id": "risk", "label": "Risk Usage", "value": _fmt_pct(rng.uniform(28, 72)), "tone": "warning", "detail": "Desk utilization"},
                {"id": "cash", "label": "Available Cash", "value": _fmt_currency(equity_values[-1] * (1 - exposure_core / 100)), "tone": "neutral", "detail": "Free capital buffer"},
            ],
            "charts": {
                "equity_curve": _build_line_points(equity_values, start, step),
                "drawdown_curve": _build_line_points(drawdown_values, start, step, precision=3),
                "pnl_distribution": _build_distribution(trade_r),
                "exposure_map": [
                    {"label": "FX majors", "value": round(exposure_core, 2)},
                    {"label": "Index hedge", "value": round(rng.uniform(8, 22), 2)},
                    {"label": "Cash buffer", "value": round(max(5.0, 100 - exposure_core - rng.uniform(8, 22)), 2)},
                ],
            },
            "recent_signals": [
                {
                    "id": f"sig-{index}",
                    "timestamp": (now - timedelta(minutes=index * 18)).isoformat(),
                    "symbol": rng.choice(["EURUSD", "NAS100", "XAUUSD", "GBPUSD"]),
                    "side": rng.choice(["BUY", "SELL"]),
                    "status": rng.choice(["EXECUTED", "BLOCKED", "IGNORED"]),
                    "price": round(rng.uniform(1.02, 20850), 4),
                    "reason": rng.choice([
                        "Trend alignment",
                        "News blackout active",
                        "Spread guard triggered",
                        "Session filter rejected",
                    ]),
                }
                for index in range(1, 8)
            ],
            "open_positions": [
                {
                    "id": f"pos-{index}",
                    "symbol": rng.choice(["EURUSD", "XAUUSD", "US30"]),
                    "side": rng.choice(["LONG", "SHORT"]),
                    "size": round(rng.uniform(0.1, 1.8), 2),
                    "entry": round(rng.uniform(1.0, 20500), 4),
                    "pnl": round(rng.uniform(-420, 760), 2),
                    "stop": round(rng.uniform(0.9, 20400), 4),
                    "take_profit": round(rng.uniform(1.1, 20800), 4),
                    "status": "OPEN",
                }
                for index in range(1, rng.randint(2, 4))
            ],
            "risk_panel": {
                "risk_usage_pct": round(rng.uniform(24, 68), 2),
                "var_proxy_pct": round(rng.uniform(1.2, 3.8), 2),
                "leverage_proxy": round(rng.uniform(1.1, 2.4), 2),
                "exposure_pct": round(exposure_core, 2),
                "daily_loss_used_pct": round(rng.uniform(18, 64), 2),
                "kill_switch_status": "NOMINAL",
                "warnings": ["Demo telemetry only — verify thresholds on real execution feed."],
                "max_drawdown_pct": round(abs(min(drawdown_values)), 2),
            },
            "market_panel": {
                "regime": rng.choice(["Trend expansion", "Compression", "Range rotation"]),
                "volatility": rng.choice(["Contained", "Elevated", "High"]),
                "session": _market_session(now),
                "news_risk_active": rng.choice([True, False]),
                "news_provider": "manual",
                "news_events": rng.randint(0, 4),
                "macro_filter_status": "Demo gating active",
                "directional_bias": rng.choice(["Neutral", "Bullish USD", "Risk-off", "Bullish indices"]),
                "warnings": ["Live macro provider not attached — control room is using simulated desk context."],
            },
            "tech_panel": {
                "data_provider": "mock-telemetry",
                "data_feed_status": "Synthetic / ready for adapter",
                "last_sync": now.isoformat(),
                "parser_status": "Ready",
                "engine_status": "Idle",
                "provider_status": "Manual simulation",
                "export_status": "No live export sync" if not selected_detail else "Artifacts available" if (selected_detail.get("artifacts") or []) else "No bundle yet",
                "last_run_label": (selected_project or {}).get("updated_at") or now.isoformat(),
                "artifacts_ready": len((selected_detail or {}).get("artifacts") or []),
                "jobs_running": len([job for job in ((selected_detail or {}).get("jobs") or []) if job.get("status") in {"queued", "running"}]),
                "latency_ms": rng.randint(19, 64),
                "warnings": ["Mock mode active until a real project run is connected."],
            },
            "insight_boxes": [
                {"label": "Strategy Health", "value": f"{strategy_health_score}/100", "tone": "positive" if strategy_health_score >= 75 else "warning", "detail": "Composite desk score"},
                {"label": "News Risk", "value": "Armed", "tone": "warning", "detail": "Macro blackout windows simulated"},
                {"label": "Daily Loss Guard", "value": "Enabled", "tone": "positive", "detail": "Loss guard remains inside policy"},
                {"label": "Safe to run?", "value": "Paper only", "tone": "warning", "detail": "Connect a live adapter before elevating to run-time usage"},
            ],
            "recent_changes": cls._recent_changes(selected_detail) or [
                "Mock dashboard feed initialized.",
                "No linked live execution adapter yet.",
                "Ready to ingest future live broker telemetry.",
            ],
            "alerts": alerts,
        }

    @classmethod
    def _recent_changes(cls, project: Optional[dict[str, Any]]) -> list[str]:
        if not project:
            return []
        versions = list(project.get("versions") or [])
        artifacts = list(project.get("artifacts") or [])
        jobs = list(project.get("jobs") or [])
        changes: list[str] = []
        for version in versions[:3]:
            changes.append(
                f"{version.get('version_kind', 'version')} archived with status {version.get('status', 'unknown')}."
            )
        if artifacts:
            changes.append(f"{len(artifacts)} artifact(s) currently linked to the project.")
        if jobs:
            latest_job = jobs[0]
            changes.append(
                f"Last job: {latest_job.get('job_type', 'workflow')} is {latest_job.get('status', 'unknown')}."
            )
        return changes[:4]
