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


def _build_line_points_between(
    values: list[float],
    start: datetime,
    end: datetime,
    precision: int = 2,
) -> list[dict[str, Any]]:
    if not values:
        return []
    if len(values) == 1 or start >= end:
        return [
            {
                "timestamp": end.isoformat(),
                "label": end.strftime("%d %b"),
                "value": round(float(values[-1]), precision),
            }
        ]
    total_seconds = max(1.0, (end - start).total_seconds())
    step_seconds = total_seconds / max(1, len(values) - 1)
    points: list[dict[str, Any]] = []
    for index, value in enumerate(values):
        ts = start + timedelta(seconds=step_seconds * index)
        points.append(
            {
                "timestamp": ts.isoformat(),
                "label": ts.strftime("%d %b"),
                "value": round(float(value), precision),
            }
        )
    return points


def _parse_optional_datetime(value: Optional[str], fallback: datetime, *, end_of_day: bool = False) -> datetime:
    if not value:
        return fallback
    raw = str(value).strip()
    if not raw:
        return fallback
    try:
        if len(raw) == 10:
            suffix = "23:59:59.999999+00:00" if end_of_day else "00:00:00+00:00"
            return datetime.fromisoformat(f"{raw}T{suffix}")
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return fallback


def _filter_points_by_window(
    points: list[dict[str, Any]],
    *,
    date_from: Optional[str],
    date_to: Optional[str],
) -> list[dict[str, Any]]:
    if not points:
        return []
    start = _parse_optional_datetime(date_from, datetime.min.replace(tzinfo=timezone.utc))
    end = _parse_optional_datetime(date_to, datetime.max.replace(tzinfo=timezone.utc), end_of_day=True)
    filtered: list[dict[str, Any]] = []
    for item in points:
        timestamp = _parse_optional_datetime(item.get("timestamp"), datetime.min.replace(tzinfo=timezone.utc))
        if start <= timestamp <= end:
            filtered.append(item)
    if filtered:
        return filtered
    if date_from or date_to:
        return []
    return points


def _timeframe_delta(timeframe: str) -> timedelta:
    mapping = {
        "7D": timedelta(days=7),
        "30D": timedelta(days=30),
        "90D": timedelta(days=90),
    }
    return mapping.get(str(timeframe).upper(), timedelta(days=30))


def _resolve_window(
    timeframe: str,
    *,
    date_from: Optional[str],
    date_to: Optional[str],
    fallback_start: datetime,
    fallback_end: datetime,
) -> tuple[datetime, datetime]:
    if fallback_end < fallback_start:
        fallback_end = fallback_start

    end = _parse_optional_datetime(date_to, fallback_end, end_of_day=True) if date_to else fallback_end
    if end > fallback_end:
        end = fallback_end
    if end < fallback_start:
        end = fallback_start

    default_start = end - _timeframe_delta(timeframe)
    start = _parse_optional_datetime(date_from, default_start) if date_from else default_start
    if start < fallback_start:
        start = fallback_start
    if start > end:
        start = end

    return start, end


def _window_label(date_from: Optional[str], date_to: Optional[str], fallback: str) -> str:
    if date_from and date_to:
        return f"{date_from} → {date_to}"
    if date_from:
        return f"da {date_from}"
    if date_to:
        return f"fino a {date_to}"
    return fallback


def _filter_trade_records_by_window(
    trades: list[dict[str, Any]],
    *,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for trade in trades:
        if not isinstance(trade, dict):
            continue
        raw_timestamp = trade.get("exit_time") or trade.get("entry_time") or trade.get("timestamp")
        timestamp = _parse_optional_datetime(raw_timestamp, datetime.min.replace(tzinfo=timezone.utc))
        if start <= timestamp <= end:
            filtered.append(trade)
    return filtered


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
        return "Qualità istituzionale"
    if score >= 0.68:
        return "Candidata stabile"
    if score >= 0.52:
        return "Richiede supervisione"
    return "Fragile / sperimentale"


class DashboardService:
    @classmethod
    async def get_command_center(
        cls,
        *,
        owner_username: str,
        project_id: Optional[str] = None,
        timeframe: str = "30D",
        source: str = "auto",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> dict[str, Any]:
        projects = await ProjectStore.list_projects(owner_username)
        selected_project = await cls._resolve_project(owner_username, projects, project_id)
        selected_detail = (
            await ProjectStore.get_project(owner_username, selected_project["project_id"])
            if selected_project
            else None
        )
        live_monitor_config = await cls._live_monitor_config(selected_project)
        live_snapshots = await cls._load_live_monitor_snapshots(selected_detail)

        if source == "demo":
            payload = cls._build_mock_response(
                projects=projects,
                selected_project=selected_project,
                selected_detail=selected_detail,
                timeframe=timeframe,
                date_from=date_from,
                date_to=date_to,
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
                    live_snapshots=live_snapshots,
                    timeframe=timeframe,
                    date_from=date_from,
                    date_to=date_to,
                )
                payload["live_monitor"] = live_monitor_config
                return payload
            formal_spec_payload = await cls._load_formal_spec_payload(selected_detail)
            real_payload = await cls._load_real_backtest_payload(selected_detail)
            payload = cls._build_shadow_live_response(
                projects=projects,
                selected_project=selected_project,
                selected_detail=selected_detail,
                formal_spec_payload=formal_spec_payload,
                backtest_payload=real_payload,
                timeframe=timeframe,
                date_from=date_from,
                date_to=date_to,
            )
            if payload:
                payload["live_monitor"] = {
                    **(live_monitor_config or {}),
                    "connected": True,
                    "mode": "Mercato live automatico",
                    "first_ingest_at": payload.get("data_window", {}).get("date_from"),
                    "last_ingest_at": payload.get("as_of"),
                }
                return payload
            payload = cls._build_mock_response(
                projects=projects,
                selected_project=selected_project,
                selected_detail=selected_detail,
                timeframe=timeframe,
                date_from=date_from,
                date_to=date_to,
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
                live_snapshots=live_snapshots,
                timeframe=timeframe,
                date_from=date_from,
                date_to=date_to,
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
                date_from=date_from,
                date_to=date_to,
            )
            payload["live_monitor"] = live_monitor_config
            return payload

        payload = cls._build_mock_response(
            projects=projects,
            selected_project=selected_project,
            selected_detail=selected_detail,
            timeframe=timeframe,
            date_from=date_from,
            date_to=date_to,
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
    async def _load_formal_spec_payload(cls, project: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if not project:
            return None
        active_session_id = project.get("active_session_id")
        if active_session_id:
            stored = InMemorySessionStore.get(active_session_id, "formal_spec_bundle")
            if isinstance(stored, dict) and stored.get("status") == "VALID":
                return stored
            botlab = InMemorySessionStore.get(active_session_id, "bot_lab_bundle") or {}
            analysis = dict(botlab.get("analysis") or {})
            bundle = analysis.get("formal_spec_bundle")
            if isinstance(bundle, dict) and bundle.get("status") == "VALID":
                return bundle

        latest = await ProjectStore.get_latest_version(project["project_id"], version_kind="formal_spec")
        if latest and isinstance(latest.get("payload"), dict):
            return latest["payload"]

        latest_bot_upload = await ProjectStore.get_latest_version(project["project_id"], version_kind="bot_upload_analysis")
        upload_payload = dict((latest_bot_upload or {}).get("payload") or {})
        bundle = upload_payload.get("formal_spec_bundle")
        if isinstance(bundle, dict) and bundle.get("status") == "VALID":
            return bundle
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
    async def _load_live_monitor_snapshots(cls, project: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
        if not project:
            return []
        versions = await ProjectStore.list_version_payloads(
            project["project_id"],
            version_kind="live_monitor_snapshot",
            limit=240,
        )
        snapshots: list[dict[str, Any]] = []
        for version in reversed(versions):
            payload = dict(version.get("payload") or {})
            timestamp = payload.get("timestamp") or version.get("created_at")
            if not isinstance(payload.get("equity"), (int, float)):
                continue
            snapshots.append(
                {
                    **payload,
                    "timestamp": timestamp,
                    "created_at": version.get("created_at"),
                }
            )
        return snapshots

    @classmethod
    async def _live_monitor_config(cls, project: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if not project:
            return None
        metadata = dict(project.get("metadata") or {})
        snapshots = await cls._load_live_monitor_snapshots(project)
        return {
            "project_id": project["project_id"],
            "last_ingest_at": metadata.get("last_live_ingest_at"),
            "first_ingest_at": snapshots[0].get("timestamp") if snapshots else None,
            "connected": bool(metadata.get("last_live_ingest_at")),
            "mode": "Telemetria progetto" if metadata.get("last_live_ingest_at") else "Monitor automatico",
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
        date_from: Optional[str],
        date_to: Optional[str],
    ) -> dict[str, Any]:
        now = _utc_now()
        oos = dict(backtest_payload.get("out_of_sample") or {})
        risk = dict(backtest_payload.get("risk_review") or {})
        regime = dict(backtest_payload.get("regime_analysis") or {})
        robustness = dict(backtest_payload.get("robustness_suite") or {})
        final_decision = dict(backtest_payload.get("final_decision") or {})
        data_info = dict(backtest_payload.get("data_info") or {})
        calendar_context = dict(data_info.get("calendar_context") or {})
        cfg_snapshot = dict((backtest_payload.get("research_governance") or {}).get("config_snapshot") or {})
        equity_values = [float(value) for value in (oos.get("equity_curve") or []) if isinstance(value, (int, float))]
        if not equity_values:
            return cls._build_mock_response(
                projects=projects,
                selected_project=selected_project,
                selected_detail=selected_detail,
                timeframe=timeframe,
                date_from=date_from,
                date_to=date_to,
                forced=True,
            )

        raw_start = cfg_snapshot.get("date_oos_start") or cfg_snapshot.get("date_from")
        raw_end = cfg_snapshot.get("date_to")
        period_start = _parse_optional_datetime(raw_start, now - timedelta(days=30))
        period_end = _parse_optional_datetime(raw_end, now, end_of_day=True)
        window_start, window_end = _resolve_window(
            timeframe,
            date_from=date_from,
            date_to=date_to,
            fallback_start=period_start,
            fallback_end=period_end,
        )
        full_equity_curve = _build_line_points_between(equity_values, period_start, period_end)
        equity_curve = _filter_points_by_window(
            full_equity_curve,
            date_from=window_start.isoformat(),
            date_to=window_end.isoformat(),
        )
        filtered_values = [point["value"] for point in equity_curve]
        if not filtered_values:
            filtered_values = equity_values
            equity_curve = full_equity_curve
            window_start = period_start
            window_end = period_end
        drawdown_curve = _build_line_points_between(
            _compute_drawdown_series(filtered_values),
            _parse_optional_datetime(equity_curve[0]["timestamp"], window_start) if equity_curve else window_start,
            _parse_optional_datetime(equity_curve[-1]["timestamp"], window_end) if equity_curve else window_end,
            precision=3,
        )

        trades = _filter_trade_records_by_window(
            list(oos.get("trades") or []),
            start=window_start,
            end=window_end,
        )
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
        period_return_pct = ((filtered_values[-1] / filtered_values[0]) - 1) * 100 if len(filtered_values) > 1 and filtered_values[0] else 0.0
        filtered_drawdown_values = [float(point["value"]) for point in drawdown_curve]
        filtered_max_drawdown = min(filtered_drawdown_values) if filtered_drawdown_values else 0.0
        winning_trades = len([value for value in trade_r if value > 0])
        hit_rate_pct = (winning_trades / len(trade_r) * 100) if trade_r else 0.0
        warnings = [
            *((final_decision.get("warnings") or [])[:3]),
            *((risk.get("warnings") or [])[:2]),
            *((calendar_context.get("warnings") or [])[:2]),
        ]
        alerts = [
            {
                "tone": "warning" if "warning" in label.lower() else "info",
                "title": "Nota operativa",
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
            "data_window": {
                "mode": "real",
                "label": _window_label(window_start.date().isoformat(), window_end.date().isoformat(), timeframe),
                "date_from": window_start.date().isoformat(),
                "date_to": window_end.date().isoformat(),
                "note": "Storico: il desk usa il backtest reale collegato al progetto nella finestra temporale selezionata.",
            },
            "header": {
                "bot_label": project_title,
                "status": "REVISIONE BACKTEST",
                "status_tone": "neutral",
                "current_time": now.isoformat(),
                "market_session": _market_session(now),
                "connection_status": "Storico collegato",
                "connection_tone": "positive",
                "strategy_health_label": _strategy_health_label(overall_score),
                "strategy_health_score": strategy_health_score,
                "desk_mode": "Revisione / validazione",
                "source_label": "Backtest reale",
            },
            "kpis": [
                {"id": "equity", "label": "Equity finale", "value": _fmt_currency(filtered_values[-1]), "tone": "neutral", "detail": "Capitale finale nella finestra"},
                {"id": "pnl", "label": "PnL periodo", "value": _fmt_pct(period_return_pct), "tone": "positive" if period_return_pct >= 0 else "negative", "detail": "Performance della finestra selezionata"},
                {"id": "positions", "label": "Posizioni aperte", "value": "0", "tone": "neutral", "detail": "In revisione non ci sono posizioni live"},
                {"id": "winrate", "label": "Win rate", "value": _fmt_pct(hit_rate_pct), "tone": "neutral", "detail": "Trade eseguiti nella finestra"},
                {"id": "drawdown", "label": "Max drawdown", "value": _fmt_pct(filtered_max_drawdown), "tone": "negative", "detail": "Peggior compressione dell’equity"},
                {"id": "quality", "label": "Punteggio qualità", "value": f"{strategy_health_score}/100", "tone": "positive" if strategy_health_score >= 70 else "warning", "detail": final_decision.get("confidence_label") or "Confidenza ricerca"},
                {"id": "risk", "label": "Uso rischio", "value": _fmt_pct(float((risk.get("metrics") or {}).get("variance_pressure_score") or 0.0) * 100), "tone": "warning", "detail": "Proxy pressione varianza"},
                {"id": "cash", "label": "Capitale disponibile", "value": _fmt_currency(filtered_values[-1] * (1 - min(0.85, float((risk.get("metrics") or {}).get("risk_concentration_pct") or 0.0) / 100))), "tone": "neutral", "detail": "Capitale approssimativamente deployabile"},
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
                "max_drawdown_pct": round(abs(filtered_max_drawdown), 2),
            },
            "market_panel": {
                "regime": ((regime.get("by_regime") or [{}])[0] or {}).get("regime") or "Mixed",
                "volatility": ((regime.get("by_regime") or [{}])[0] or {}).get("volatility_regime") or "Unknown",
                "session": _market_session(now),
                "news_risk_active": bool(calendar_context.get("events_used")),
                "news_provider": calendar_context.get("provider") or "none",
                "news_events": int(calendar_context.get("events_used") or 0),
                "macro_filter_status": "Attivo" if (calendar_context.get("provider") or "none") != "none" else "Inattivo",
                "directional_bias": (data_info.get("calendar_context") or {}).get("directional_bias") or "Neutrale",
                "warnings": calendar_context.get("warnings") or [],
            },
            "tech_panel": {
                "data_provider": data_info.get("provider") or "unknown",
                "data_feed_status": "Stabile",
                "last_sync": (selected_project or {}).get("updated_at") or now.isoformat(),
                "parser_status": "Validato" if any(version.get("version_kind") == "parse_result" for version in ((selected_detail or {}).get("versions") or [])) else "N/D",
                "engine_status": "Pronto",
                "provider_status": "Configurato" if (calendar_context.get("provider") or "none") != "none" else "Nessun provider macro",
                "export_status": "Pacchetto pronto" if export_ready else "Nessun bundle",
                "last_run_label": backtest_payload.get("research_governance", {}).get("analysis_timestamp") or now.isoformat(),
                "artifacts_ready": len(project_artifacts),
                "jobs_running": running_jobs,
                "latency_ms": 28,
                "warnings": data_info.get("quality_warnings") or [],
            },
            "insight_boxes": [
                {"label": "Salute strategia", "value": f"{strategy_health_score}/100", "tone": "positive" if strategy_health_score >= 70 else "warning", "detail": _strategy_health_label(overall_score)},
                {"label": "Rischio news", "value": "Attivo" if bool(calendar_context.get("events_used")) else "Inattivo", "tone": "warning" if bool(calendar_context.get("events_used")) else "neutral", "detail": f"{int(calendar_context.get('events_used') or 0)} finestre macro programmate"},
                {"label": "Robustezza", "value": f"{round(float(robustness.get('robustness_score') or 0.0) * 100)} / 100", "tone": "positive" if float(robustness.get("robustness_score") or 0.0) >= 0.7 else "warning", "detail": robustness.get("summary") or "Profilo di stress e degradazione"},
                {"label": "Pronta al live?", "value": "Controllata" if final_decision.get("export_allowed") else "Bloccata", "tone": "positive" if final_decision.get("export_allowed") else "negative", "detail": "; ".join((final_decision.get("reasons") or final_decision.get("blockers") or ["Review richiesta"]))},
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
        live_snapshots: list[dict[str, Any]],
        timeframe: str,
        date_from: Optional[str],
        date_to: Optional[str],
    ) -> dict[str, Any]:
        now = _utc_now()
        metadata = dict((selected_project or {}).get("metadata") or {})
        first_snapshot_at = _parse_optional_datetime(
            live_snapshots[0].get("timestamp"),
            now - _timeframe_delta(timeframe),
        ) if live_snapshots else now - _timeframe_delta(timeframe)
        window_start, window_end = _resolve_window(
            timeframe,
            date_from=date_from,
            date_to=date_to,
            fallback_start=first_snapshot_at,
            fallback_end=now,
        )
        filtered_snapshots = []
        if live_snapshots:
            for item in live_snapshots:
                timestamp = _parse_optional_datetime(item.get("timestamp"), now)
                if window_start <= timestamp <= window_end:
                    filtered_snapshots.append(item)
        selected_live_payload = filtered_snapshots[-1] if filtered_snapshots else live_payload
        project_title = (selected_project or {}).get("title") or selected_live_payload.get("bot_label") or "Monitor live"
        equity_curve = [float(item.get("equity") or 0.0) for item in filtered_snapshots if isinstance(item.get("equity"), (int, float))]
        if not equity_curve:
            equity_curve = list(selected_live_payload.get("equity_curve") or [])
        if not equity_curve and isinstance(selected_live_payload.get("equity"), (int, float)):
            base_equity = float(selected_live_payload.get("equity") or 0.0)
            equity_curve = [base_equity * (1 - 0.002 * i) for i in reversed(range(10))] + [base_equity]
        start = window_start
        if filtered_snapshots:
            equity_points = [
                {
                    "timestamp": item.get("timestamp") or now.isoformat(),
                    "label": _parse_optional_datetime(item.get("timestamp"), now).strftime("%d %b"),
                    "value": round(float(item.get("equity") or 0.0), 2),
                }
                for item in filtered_snapshots
            ]
        else:
            equity_points = _build_line_points_between(equity_curve, start, window_end)
        curve_values = [point["value"] for point in equity_points]
        drawdown_points = _build_line_points_between(
            _compute_drawdown_series(curve_values),
            _parse_optional_datetime(equity_points[0]["timestamp"], start) if equity_points else start,
            _parse_optional_datetime(equity_points[-1]["timestamp"], window_end) if equity_points else window_end,
            precision=3,
        )
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
            for index, item in enumerate(selected_live_payload.get("open_positions") or [], start=1)
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
            for index, item in enumerate(selected_live_payload.get("recent_signals") or [], start=1)
            if isinstance(item, dict)
        ]
        distribution_seed = [float(item.get("pnl") or 0.0) for item in open_positions] or [float(selected_live_payload.get("today_pnl_pct") or 0.0)]
        first_live_at = filtered_snapshots[0].get("timestamp") if filtered_snapshots else (live_snapshots[0].get("timestamp") if live_snapshots else metadata.get("last_live_ingest_at"))
        last_live_at = filtered_snapshots[-1].get("timestamp") if filtered_snapshots else (selected_live_payload.get("timestamp") or metadata.get("last_live_ingest_at"))

        return {
            "as_of": selected_live_payload.get("timestamp") or now.isoformat(),
            "source_mode": "live",
            "operating_mode": "LIVE",
            "selected_project_id": (selected_project or {}).get("project_id"),
            "selected_project_title": project_title,
            "available_projects": projects,
            "timeframe": timeframe,
            "data_window": {
                "mode": "live",
                "label": _window_label(window_start.date().isoformat(), None, f"da {window_start.date().isoformat()}"),
                "date_from": window_start.date().isoformat(),
                "date_to": last_live_at or window_end.date().isoformat(),
                "note": "Live: il desk usa gli snapshot ricevuti dal monitor dal momento iniziale selezionato fino ad adesso.",
            },
            "header": {
                "bot_label": selected_live_payload.get("bot_label") or project_title,
                "status": "MONITOR LIVE",
                "status_tone": "positive",
                "current_time": selected_live_payload.get("timestamp") or now.isoformat(),
                "market_session": _market_session(now),
                "connection_status": "Bridge live connesso",
                "connection_tone": "positive",
                "strategy_health_label": "Telemetria live attiva",
                "strategy_health_score": max(0, min(100, round(100 - float(selected_live_payload.get("max_drawdown_pct") or 0.0) * 3))),
                "desk_mode": "Supervisione live",
                "source_label": "Telemetria live progetto",
            },
            "kpis": [
                {"id": "equity", "label": "Equity totale", "value": _fmt_currency(float(selected_live_payload.get("equity") or 0.0)), "tone": "neutral", "detail": "Equity account corrente"},
                {"id": "pnl", "label": "PnL giornaliero", "value": _fmt_pct(float(selected_live_payload.get("today_pnl_pct") or 0.0)), "tone": "positive" if float(selected_live_payload.get("today_pnl_pct") or 0.0) >= 0 else "negative", "detail": "Andamento live del giorno"},
                {"id": "positions", "label": "Posizioni aperte", "value": str(len(open_positions)), "tone": "neutral", "detail": "Ticket live attivi"},
                {"id": "winrate", "label": "Stato feed", "value": str(selected_live_payload.get("data_feed_status") or "Live"), "tone": "positive", "detail": "Feed dati runtime"},
                {"id": "drawdown", "label": "Max drawdown", "value": _fmt_pct(float(selected_live_payload.get("max_drawdown_pct") or 0.0)), "tone": "negative", "detail": "Drawdown live"},
                {"id": "quality", "label": "Latenza", "value": f"{int(selected_live_payload.get('latency_ms') or 0)} ms", "tone": "neutral", "detail": "Latenza bridge"},
                {"id": "risk", "label": "Uso rischio", "value": _fmt_pct(float(selected_live_payload.get("risk_usage_pct") or 0.0)), "tone": "warning", "detail": "Budget rischio corrente"},
                {"id": "cash", "label": "Capitale disponibile", "value": _fmt_currency(float(selected_live_payload.get("available_cash") or selected_live_payload.get("balance") or 0.0)), "tone": "neutral", "detail": "Capitale libero live"},
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
                "risk_usage_pct": round(float(selected_live_payload.get("risk_usage_pct") or 0.0), 2),
                "var_proxy_pct": round(float(selected_live_payload.get("var_proxy_pct") or 0.0), 2),
                "leverage_proxy": round(float(selected_live_payload.get("leverage_proxy") or 1.0), 2),
                "exposure_pct": round(float(selected_live_payload.get("exposure_pct") or 0.0), 2),
                "daily_loss_used_pct": round(float(selected_live_payload.get("daily_loss_used_pct") or 0.0), 2),
                "kill_switch_status": str(selected_live_payload.get("kill_switch_status") or "NOMINAL"),
                "warnings": list(selected_live_payload.get("warnings") or []),
                "max_drawdown_pct": round(float(selected_live_payload.get("max_drawdown_pct") or 0.0), 2),
            },
            "market_panel": {
                "regime": str(selected_live_payload.get("regime") or "Sconosciuto"),
                "volatility": str(selected_live_payload.get("volatility") or "Sconosciuta"),
                "session": _market_session(now),
                "news_risk_active": bool(selected_live_payload.get("news_risk_active")),
                "news_provider": str(selected_live_payload.get("news_provider") or "none"),
                "news_events": int(selected_live_payload.get("news_events") or 0),
                "macro_filter_status": str(selected_live_payload.get("macro_filter_status") or "Inattivo"),
                "directional_bias": str(selected_live_payload.get("directional_bias") or "Neutrale"),
                "warnings": list(selected_live_payload.get("warnings") or [])[:3],
            },
            "tech_panel": {
                "data_provider": str(selected_live_payload.get("data_provider") or "mt5_bridge"),
                "data_feed_status": str(selected_live_payload.get("data_feed_status") or "Live"),
                "last_sync": selected_live_payload.get("timestamp") or metadata.get("last_live_ingest_at") or now.isoformat(),
                "parser_status": "N/D",
                "engine_status": str(selected_live_payload.get("engine_status") or "In esecuzione"),
                "provider_status": str(selected_live_payload.get("provider_status") or "Connesso"),
                "export_status": str(selected_live_payload.get("export_status") or "Pacchetto pronto"),
                "last_run_label": selected_live_payload.get("timestamp") or now.isoformat(),
                "artifacts_ready": len((selected_detail or {}).get("artifacts") or []),
                "jobs_running": len([job for job in ((selected_detail or {}).get("jobs") or []) if job.get("status") in {"queued", "running"}]),
                "latency_ms": int(selected_live_payload.get("latency_ms") or 0),
                "warnings": list(selected_live_payload.get("warnings") or []),
            },
            "insight_boxes": [
                {"label": "Feed live", "value": "Connesso", "tone": "positive", "detail": "Telemetria runtime collegata al progetto"},
                {"label": "Rischio drift", "value": "Sorveglia" if float(selected_live_payload.get("max_drawdown_pct") or 0.0) >= 8 else "Contenuto", "tone": "warning" if float(selected_live_payload.get("max_drawdown_pct") or 0.0) >= 8 else "positive", "detail": "Confronta il live con il profilo validato"},
                {"label": "Stato macro", "value": "Attivo" if bool(selected_live_payload.get("news_risk_active")) else "Inattivo", "tone": "warning" if bool(selected_live_payload.get("news_risk_active")) else "neutral", "detail": "Supervisione finestra macro live"},
                {"label": "Pronto al live?", "value": "Controllato" if str(selected_live_payload.get("kill_switch_status") or "NOMINAL") == "NOMINAL" else "Limitato", "tone": "positive" if str(selected_live_payload.get("kill_switch_status") or "NOMINAL") == "NOMINAL" else "negative", "detail": "Stato governance live"},
            ],
            "recent_changes": cls._recent_changes(selected_detail) or ["Monitor live collegato al progetto corrente."],
            "alerts": [
                {
                    "tone": "warning" if float(selected_live_payload.get("daily_loss_used_pct") or 0.0) >= 70 else "neutral",
                    "title": "Supervisione live attiva",
                    "detail": "Il desk sta leggendo snapshot live invece del solo payload di revisione.",
                }
            ],
            "live_monitor": {
                "project_id": (selected_project or {}).get("project_id"),
                "monitor_token": metadata.get("live_monitor_token"),
                "ingest_path": "/api/dashboard/live-monitor-ingest",
                "last_ingest_at": metadata.get("last_live_ingest_at") or selected_live_payload.get("timestamp"),
                "first_ingest_at": first_live_at,
                "connected": True,
                "sample_fields": ["equity", "today_pnl_pct", "risk_usage_pct", "open_positions", "recent_signals", "latency_ms"],
            },
        }

    @classmethod
    def _build_shadow_live_response(
        cls,
        *,
        projects: list[dict[str, Any]],
        selected_project: Optional[dict[str, Any]],
        selected_detail: Optional[dict[str, Any]],
        formal_spec_payload: Optional[dict[str, Any]],
        backtest_payload: Optional[dict[str, Any]],
        timeframe: str,
        date_from: Optional[str],
        date_to: Optional[str],
    ) -> Optional[dict[str, Any]]:
        if not formal_spec_payload:
            return None

        from api.routers.backtest import _build_strategy_function
        from modules.backtest.data_provider import DataProvider
        from modules.backtest.engine import BacktestConfig, BacktestEngine

        try:
            import pandas as pd
        except Exception:
            return None

        now = _utc_now()
        spec = dict(formal_spec_payload.get("formal_spec") or {})
        backtest_info = dict((backtest_payload or {}).get("data_info") or {})
        metadata = dict((selected_project or {}).get("metadata") or {})

        symbol = str(
            backtest_info.get("symbol")
            or formal_spec_payload.get("symbol")
            or spec.get("symbol")
            or spec.get("market")
            or metadata.get("latest_symbol")
            or ""
        ).strip().upper()
        execution_timeframe = str(
            spec.get("execution_timeframe")
            or spec.get("timeframe")
            or (spec.get("timeframes") or {}).get("entry")
            or backtest_info.get("timeframe")
            or metadata.get("latest_timeframe")
            or "H1"
        ).strip().upper()
        provider = str(
            backtest_info.get("provider")
            or metadata.get("latest_provider")
            or "polygon"
        ).strip().lower()
        if provider not in {"polygon", "dukascopy"}:
            provider = "polygon"
        if not symbol:
            return None

        window_end = now
        fallback_start = now - _timeframe_delta(timeframe)
        window_start, window_end = _resolve_window(
            timeframe,
            date_from=date_from,
            date_to=date_to,
            fallback_start=fallback_start,
            fallback_end=window_end,
        )
        warmup_start = window_start - max(timedelta(days=14), _timeframe_delta(timeframe))

        provider_result = DataProvider().get_ohlc(
            symbol=symbol,
            timeframe=execution_timeframe,
            date_from=warmup_start.date().isoformat(),
            date_to=window_end.date().isoformat(),
            provider=provider,
        )
        quality = dict(provider_result.get("quality") or {})
        if quality.get("provider") == "demo" or quality.get("source") == "synthetic":
            return None

        data = provider_result.get("data")
        if data is None or len(data) < 60:
            return None

        if not isinstance(data.index, pd.DatetimeIndex):
            data.index = pd.to_datetime(data.index, utc=True)
        elif data.index.tz is None:
            data.index = data.index.tz_localize("UTC")
        else:
            data.index = data.index.tz_convert("UTC")
        data = data.sort_index()
        data = data.loc[:window_end]
        if len(data) < 60:
            return None

        risk_cfg = dict(spec.get("risk_management") or {})
        initial_capital = float(
            ((backtest_payload or {}).get("research_governance") or {}).get("config_snapshot", {}).get("initial_capital")
            or 100000.0
        )
        risk_per_trade = float(
            risk_cfg.get("risk_per_trade_pct")
            or risk_cfg.get("risk_percent")
            or spec.get("risk_per_trade_pct")
            or 1.0
        )
        strategy_func = _build_strategy_function(data, formal_spec_payload, news_windows=[])
        engine = BacktestEngine(
            BacktestConfig(
                initial_capital=initial_capital,
                risk_per_trade_pct=risk_per_trade,
                symbol=symbol,
            )
        )
        result = engine.run(data, strategy_func)
        full_start = data.index[0].to_pydatetime()
        full_end = data.index[-1].to_pydatetime()
        full_equity_points = _build_line_points_between(
            [float(value) for value in (result.get("equity_curve") or []) if isinstance(value, (int, float))],
            full_start,
            full_end,
        )
        equity_points = _filter_points_by_window(
            full_equity_points,
            date_from=window_start.isoformat(),
            date_to=window_end.isoformat(),
        )
        if not equity_points:
            return None

        curve_values = [float(point["value"]) for point in equity_points]
        drawdown_values = _compute_drawdown_series(curve_values)
        drawdown_points = _build_line_points_between(
            drawdown_values,
            _parse_optional_datetime(equity_points[0]["timestamp"], window_start),
            _parse_optional_datetime(equity_points[-1]["timestamp"], window_end),
            precision=3,
        )
        trades = _filter_trade_records_by_window(
            list(result.get("trades") or []),
            start=window_start,
            end=window_end,
        )
        recent_signals = [
            {
                "id": f"shadow-sig-{index}",
                "timestamp": trade.get("entry_time") or trade.get("exit_time") or now.isoformat(),
                "symbol": symbol,
                "side": "BUY" if str(trade.get("direction") or "").upper() == "LONG" else "SELL",
                "status": "EXECUTED",
                "price": float(trade.get("entry_price") or 0.0),
                "reason": trade.get("exit_reason") or "Segnale strategia",
            }
            for index, trade in enumerate(reversed(trades[-8:]), start=1)
            if isinstance(trade, dict)
        ]

        current_signal = strategy_func(data)
        latest_close = float(data["Close"].iloc[-1])
        open_positions = []
        if current_signal and current_signal.get("signal"):
            open_positions.append(
                {
                    "id": "shadow-live-1",
                    "symbol": symbol,
                    "side": "LONG" if str(current_signal.get("signal")).upper() == "LONG" else "SHORT",
                    "size": round(max(0.01, risk_per_trade / 2), 2),
                    "entry": round(latest_close, 5),
                    "pnl": 0.0,
                    "stop": round(float(current_signal.get("sl") or 0.0), 5),
                    "take_profit": round(float(current_signal.get("tp") or 0.0), 5),
                    "status": "MODEL",
                }
            )

        close_returns = data["Close"].pct_change().dropna()
        atr_proxy = ((data["High"] - data["Low"]) / data["Close"]).tail(20).mean() if len(data) >= 20 else 0.0
        momentum = ((data["Close"].iloc[-1] / data["Close"].iloc[max(0, len(data) - 20)]) - 1) if len(data) >= 20 else 0.0
        regime = "Trend" if abs(momentum) >= max(0.004, float(atr_proxy or 0.0) * 2.2) else "Range"
        volatility_label = "Alta" if float(atr_proxy or 0.0) >= 0.012 else "Media" if float(atr_proxy or 0.0) >= 0.006 else "Contenuta"
        latest_drawdown = min(drawdown_values) if drawdown_values else 0.0
        recent_return = ((curve_values[-1] / curve_values[0]) - 1) * 100 if len(curve_values) > 1 and curve_values[0] else 0.0
        win_count = len([trade for trade in trades if float(trade.get("r_multiple") or 0.0) > 0])
        hit_rate = (win_count / len(trades) * 100) if trades else 0.0
        final_capital = curve_values[-1]
        available_cash = final_capital * (0.82 if open_positions else 0.94)
        risk_usage = min(95.0, abs(latest_drawdown) * 4.0 + len(open_positions) * 12.0 + risk_per_trade * 8.0)
        daily_loss_used = min(100.0, abs(latest_drawdown) * 5.0)
        var_proxy = abs(close_returns.tail(12).min() * 100) if len(close_returns) >= 12 else abs(recent_return) / 4
        leverage_proxy = 1.0 + min(1.8, len(open_positions) * 0.45 + risk_per_trade / 3)
        exposure_pct = min(100.0, len(open_positions) * 24.0 + risk_per_trade * 10.0)
        strategy_health_score = max(0, min(100, round(78 + recent_return * 2.5 - abs(latest_drawdown) * 2.1)))
        export_ready = any(artifact.get("artifact_type") == "bundle_manifest" for artifact in ((selected_detail or {}).get("artifacts") or []))
        provider_warnings = list(provider_result.get("warnings") or [])

        return {
            "as_of": now.isoformat(),
            "source_mode": "live",
            "operating_mode": "LIVE",
            "selected_project_id": (selected_project or {}).get("project_id"),
            "selected_project_title": (selected_project or {}).get("title") or symbol,
            "available_projects": projects,
            "timeframe": timeframe,
            "data_window": {
                "mode": "live",
                "label": _window_label(window_start.date().isoformat(), None, timeframe),
                "date_from": window_start.date().isoformat(),
                "date_to": window_end.date().isoformat(),
                "note": "Live automatico: il desk usa dati di mercato reali del progetto senza richiedere collegamenti manuali all'utente.",
            },
            "header": {
                "bot_label": (selected_project or {}).get("title") or symbol,
                "status": "MONITOR LIVE",
                "status_tone": "positive",
                "current_time": now.isoformat(),
                "market_session": _market_session(now),
                "connection_status": "Feed reale automatico",
                "connection_tone": "positive",
                "strategy_health_label": "Monitor runtime automatico",
                "strategy_health_score": strategy_health_score,
                "desk_mode": "Supervisione live automatica",
                "source_label": f"{str(quality.get('provider') or provider).upper()} · mercato reale",
            },
            "kpis": [
                {"id": "equity", "label": "Equity totale", "value": _fmt_currency(final_capital), "tone": "neutral", "detail": "Equity modello live"},
                {"id": "pnl", "label": "PnL periodo", "value": _fmt_pct(recent_return), "tone": "positive" if recent_return >= 0 else "negative", "detail": "Finestra live selezionata"},
                {"id": "positions", "label": "Posizioni aperte", "value": str(len(open_positions)), "tone": "neutral", "detail": "Posizioni modello correnti"},
                {"id": "winrate", "label": "Win rate", "value": _fmt_pct(hit_rate), "tone": "neutral", "detail": "Segnali eseguiti nella finestra"},
                {"id": "drawdown", "label": "Max drawdown", "value": _fmt_pct(latest_drawdown), "tone": "negative", "detail": "Compressione nella finestra live"},
                {"id": "quality", "label": "Punteggio qualità", "value": f"{strategy_health_score}/100", "tone": "positive" if strategy_health_score >= 70 else "warning", "detail": "Coerenza live vs logica validata"},
                {"id": "risk", "label": "Uso rischio", "value": _fmt_pct(risk_usage), "tone": "warning", "detail": "Budget rischio runtime"},
                {"id": "cash", "label": "Capitale disponibile", "value": _fmt_currency(available_cash), "tone": "neutral", "detail": "Buffer modello disponibile"},
            ],
            "charts": {
                "equity_curve": equity_points,
                "drawdown_curve": drawdown_points,
                "pnl_distribution": _build_distribution([float(trade.get("r_multiple") or 0.0) for trade in trades]),
                "exposure_map": [
                    {"label": symbol, "value": round(exposure_pct, 2)},
                    {"label": "Cash buffer", "value": round(max(0.0, 100.0 - exposure_pct), 2)},
                ],
            },
            "recent_signals": recent_signals,
            "open_positions": open_positions,
            "risk_panel": {
                "risk_usage_pct": round(risk_usage, 2),
                "var_proxy_pct": round(var_proxy, 2),
                "leverage_proxy": round(leverage_proxy, 2),
                "exposure_pct": round(exposure_pct, 2),
                "daily_loss_used_pct": round(daily_loss_used, 2),
                "kill_switch_status": "NOMINAL" if daily_loss_used < 80 else "LIMITED",
                "warnings": provider_warnings[:2],
                "max_drawdown_pct": round(abs(latest_drawdown), 2),
            },
            "market_panel": {
                "regime": regime,
                "volatility": volatility_label,
                "session": _market_session(now),
                "news_risk_active": False,
                "news_provider": "automatico",
                "news_events": 0,
                "macro_filter_status": "Non collegato",
                "directional_bias": "Neutrale",
                "warnings": provider_warnings[:2] or ["Monitor live automatico basato sul feed di mercato reale del progetto."],
            },
            "tech_panel": {
                "data_provider": str(quality.get("provider") or provider),
                "data_feed_status": "Mercato live",
                "last_sync": now.isoformat(),
                "parser_status": "Spec valida",
                "engine_status": "Monitor automatico attivo",
                "provider_status": "Feed applicazione",
                "export_status": "Pacchetto pronto" if export_ready else "Pacchetto non pronto",
                "last_run_label": now.isoformat(),
                "artifacts_ready": len((selected_detail or {}).get("artifacts") or []),
                "jobs_running": len([job for job in ((selected_detail or {}).get("jobs") or []) if job.get("status") in {"queued", "running"}]),
                "latency_ms": 0,
                "warnings": provider_warnings[:2],
            },
            "insight_boxes": [
                {"label": "Feed live", "value": "Automatico", "tone": "positive", "detail": "Mercato reale letto direttamente dalla piattaforma"},
                {"label": "Rischio drift", "value": "Sorveglia" if abs(latest_drawdown) >= 8 else "Contenuto", "tone": "warning" if abs(latest_drawdown) >= 8 else "positive", "detail": "Controllo continuo vs logica validata"},
                {"label": "Stato macro", "value": "Simulato", "tone": "neutral", "detail": "Contesto macro sintetico del desk"},
                {"label": "Pronta al live?", "value": "Controllata" if export_ready else "Pre-lancio", "tone": "positive" if export_ready else "warning", "detail": "Monitor automatico senza setup utente"},
            ],
            "recent_changes": cls._recent_changes(selected_detail) or ["Monitor live automatico attivo sul progetto corrente."],
            "alerts": [
                {
                    "tone": "neutral",
                    "title": "Monitor live automatico",
                    "detail": "Il desk usa il feed reale di mercato del progetto e non richiede collegamenti manuali dell'utente.",
                },
                *[
                    {
                        "tone": "warning",
                        "title": "Qualità feed",
                        "detail": item,
                    }
                    for item in provider_warnings[:2]
                ],
            ],
        }

    @classmethod
    def _build_mock_response(
        cls,
        *,
        projects: list[dict[str, Any]],
        selected_project: Optional[dict[str, Any]],
        selected_detail: Optional[dict[str, Any]],
        timeframe: str,
        date_from: Optional[str],
        date_to: Optional[str],
        forced: bool,
    ) -> dict[str, Any]:
        now = _utc_now()
        seed_source = (selected_project or {}).get("project_id") or (selected_project or {}).get("title") or "control-room-demo"
        seed = int(hashlib.sha256(str(seed_source).encode("utf-8")).hexdigest()[:8], 16)
        rng = random.Random(seed)

        fallback_start = now - timedelta(days=120)
        window_start, window_end = _resolve_window(
            timeframe,
            date_from=date_from,
            date_to=date_to,
            fallback_start=fallback_start,
            fallback_end=now,
        )
        total_seconds = max(3600.0, (window_end - window_start).total_seconds())
        point_count = 48 if total_seconds <= 7 * 86400 else 72 if total_seconds <= 30 * 86400 else 96
        base = 100000 + rng.randint(-6000, 6000)
        equity_values: list[float] = []
        current = float(base)
        for index in range(point_count):
            drift = rng.uniform(-0.009, 0.015)
            if index and index % 17 == 0:
                drift -= rng.uniform(0.01, 0.024)
            current *= 1 + drift
            equity_values.append(current)
        start = window_start
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
                    "title": "Dati reali non disponibili",
                    "detail": "Il desk sta mostrando un feed mock professionale perché al progetto selezionato non è ancora associata una run valida.",
                }
            )
        if min(drawdown_values) < -8:
            alerts.append(
                {
                    "tone": "warning",
                    "title": "Sorveglia il drawdown",
                    "detail": "La compressione simulata dell’equity ha superato la banda di attenzione interna. Il kill switch resta nominale.",
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
            "data_window": {
                "mode": "mock",
                "label": _window_label(window_start.date().isoformat(), window_end.date().isoformat(), timeframe),
                "date_from": window_start.date().isoformat(),
                "date_to": window_end.date().isoformat(),
                "note": "Mock: il desk usa una simulazione coerente con la finestra selezionata finché il progetto non dispone di dati reali.",
            },
            "header": {
                "bot_label": current_project_title,
                "status": "DESK PAPER" if selected_project else "DESK DEMO",
                "status_tone": "positive" if selected_project else "warning",
                "current_time": now.isoformat(),
                "market_session": _market_session(now),
                "connection_status": "Bridge mock",
                "connection_tone": "warning",
                "strategy_health_label": _strategy_health_label(strategy_health_score / 100),
                "strategy_health_score": strategy_health_score,
                "desk_mode": "Anteprima control room",
                "source_label": "Feed demo professionale",
            },
            "kpis": [
                {"id": "equity", "label": "Equity totale", "value": _fmt_currency(equity_values[-1]), "tone": "neutral", "detail": "Equity account simulata"},
                {"id": "pnl", "label": "PnL giornaliero", "value": _fmt_pct(((equity_values[-1] / equity_values[-5]) - 1) * 100), "tone": "positive" if equity_values[-1] >= equity_values[-5] else "negative", "detail": "Ultimo movimento del desk"},
                {"id": "positions", "label": "Posizioni aperte", "value": str(rng.randint(1, 4)), "tone": "neutral", "detail": "Ticket attivi simulati"},
                {"id": "winrate", "label": "Win rate", "value": _fmt_pct(rng.uniform(48, 66)), "tone": "neutral", "detail": "Hit rate rolling"},
                {"id": "drawdown", "label": "Max drawdown", "value": _fmt_pct(min(drawdown_values)), "tone": "negative", "detail": "Peak-to-trough simulato"},
                {"id": "quality", "label": "Punteggio qualità", "value": f"{strategy_health_score}/100", "tone": "positive" if strategy_health_score >= 75 else "warning", "detail": "Composito salute"},
                {"id": "risk", "label": "Uso rischio", "value": _fmt_pct(rng.uniform(28, 72)), "tone": "warning", "detail": "Utilizzo desk"},
                {"id": "cash", "label": "Capitale disponibile", "value": _fmt_currency(equity_values[-1] * (1 - exposure_core / 100)), "tone": "neutral", "detail": "Buffer capitale libero"},
            ],
            "charts": {
                "equity_curve": _build_line_points_between(equity_values, start, window_end),
                "drawdown_curve": _build_line_points_between(drawdown_values, start, window_end, precision=3),
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
                "warnings": ["Telemetria demo: verifica le soglie sul feed esecutivo reale."],
                "max_drawdown_pct": round(abs(min(drawdown_values)), 2),
            },
            "market_panel": {
                "regime": rng.choice(["Espansione trend", "Compressione", "Rotazione laterale"]),
                "volatility": rng.choice(["Contenuta", "Elevata", "Alta"]),
                "session": _market_session(now),
                "news_risk_active": rng.choice([True, False]),
                "news_provider": "manual",
                "news_events": rng.randint(0, 4),
                "macro_filter_status": "Filtro demo attivo",
                "directional_bias": rng.choice(["Neutrale", "USD rialzista", "Risk-off", "Indici rialzisti"]),
                "warnings": ["Il contesto macro del desk è simulato."],
            },
            "tech_panel": {
                "data_provider": "desk-mock",
                "data_feed_status": "Sintetico / pronto per monitor",
                "last_sync": now.isoformat(),
                "parser_status": "Pronto",
                "engine_status": "In attesa",
                "provider_status": "Simulazione manuale",
                "export_status": "Nessuna sync export live" if not selected_detail else "Artefatti disponibili" if (selected_detail.get("artifacts") or []) else "Nessun bundle",
                "last_run_label": (selected_project or {}).get("updated_at") or now.isoformat(),
                "artifacts_ready": len((selected_detail or {}).get("artifacts") or []),
                "jobs_running": len([job for job in ((selected_detail or {}).get("jobs") or []) if job.get("status") in {"queued", "running"}]),
                "latency_ms": rng.randint(19, 64),
                "warnings": ["Modalità mock attiva finché non esiste una run reale del progetto."],
            },
            "insight_boxes": [
                {"label": "Salute strategia", "value": f"{strategy_health_score}/100", "tone": "positive" if strategy_health_score >= 75 else "warning", "detail": "Punteggio composito del desk"},
                {"label": "Rischio news", "value": "Attivo", "tone": "warning", "detail": "Finestre macro simulate"},
                {"label": "Guardia perdita", "value": "Attiva", "tone": "positive", "detail": "Loss guard dentro policy"},
                {"label": "Pronta al live?", "value": "Solo paper", "tone": "warning", "detail": "Passa al monitor live quando il progetto è pronto"},
            ],
            "recent_changes": cls._recent_changes(selected_detail) or [
                "Feed mock del desk inizializzato.",
                "Monitor live non ancora attivo.",
                "Pronto a usare dati reali del progetto appena disponibili.",
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
                f"{version.get('version_kind', 'versione')} archiviata con stato {version.get('status', 'sconosciuto')}."
            )
        if artifacts:
            changes.append(f"{len(artifacts)} artefatti attualmente collegati al progetto.")
        if jobs:
            latest_job = jobs[0]
            changes.append(
                f"Ultimo job: {latest_job.get('job_type', 'workflow')} in stato {latest_job.get('status', 'sconosciuto')}."
            )
        return changes[:4]
