"""
Economic calendar provider layer.

Provider disponibili:
- none: filtri news disattivati / fallback pulito
- manual: eventi manuali o demo deterministici, utile per test e setup senza API
- trading_economics: provider esterno opzionale via env
- forexfactory / bloomberg / morningstar / investing / fxstreet:
  opzioni visibili in UI ma non integrate automaticamente in modo affidabile
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Any

import httpx


def _provider_catalog() -> list[dict[str, Any]]:
    te_api_key = (os.getenv("TRADING_ECONOMICS_API_KEY") or "").strip()
    return [
        {
            "id": "none",
            "name": "Nessun provider",
            "available": True,
            "api_key_required": False,
            "integration_status": "live",
            "description": "Nessun filtro macro applicato. Il backtest continua senza crash.",
        },
        {
            "id": "manual",
            "name": "Manual / Demo news events",
            "available": True,
            "api_key_required": False,
            "integration_status": "demo",
            "description": "Usa eventi inseriti manualmente o eventi demo deterministicamente generati.",
        },
        {
            "id": "trading_economics",
            "name": "Trading Economics",
            "available": bool(te_api_key),
            "api_key_required": True,
            "integration_status": "live" if te_api_key else "requires_config",
            "description": "Provider esterno opzionale per calendario economico. Richiede env TRADING_ECONOMICS_API_KEY.",
        },
        {
            "id": "forexfactory",
            "name": "Forex Factory",
            "available": False,
            "api_key_required": False,
            "integration_status": "restricted",
            "description": "Calendario retail molto usato. L'accesso automatico diretto oggi è protetto da challenge anti-bot, quindi non è interrogabile in modo affidabile dal backend.",
        },
        {
            "id": "bloomberg",
            "name": "Bloomberg",
            "available": False,
            "api_key_required": False,
            "integration_status": "restricted",
            "description": "Fonte premium/proprietaria. La web property pubblica non è adatta come feed calendario integrabile direttamente in questa build.",
        },
        {
            "id": "morningstar",
            "name": "Morningstar",
            "available": False,
            "api_key_required": False,
            "integration_status": "restricted",
            "description": "Fonte macro/market research utile come riferimento, ma non c'è un feed calendario automatico affidabile collegato a questa app.",
        },
        {
            "id": "investing",
            "name": "Investing.com",
            "available": False,
            "api_key_required": False,
            "integration_status": "restricted",
            "description": "Fonte retail molto diffusa. L'accesso automatico diretto non è attivato in questa build per evitare scraping fragile.",
        },
        {
            "id": "fxstreet",
            "name": "FXStreet",
            "available": False,
            "api_key_required": False,
            "integration_status": "restricted",
            "description": "Fonte utile per calendario/news FX. Provider mostrato in UI ma non ancora integrato come feed live nel backend.",
        },
    ]


def list_calendar_providers() -> list[dict[str, Any]]:
    return _provider_catalog()


def provider_status(provider_id: str) -> dict[str, Any]:
    for provider in _provider_catalog():
        if provider["id"] == provider_id:
            return provider
    return {"id": provider_id, "name": provider_id, "available": False, "api_key_required": False}


async def fetch_calendar_events(
    *,
    provider_id: str,
    date_from: str,
    date_to: str,
    currencies: list[str] | None = None,
    impacts: list[str] | None = None,
    manual_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    provider_id = (provider_id or "none").strip() or "none"
    currencies = [currency.upper() for currency in (currencies or []) if currency]
    impacts = [impact.lower() for impact in (impacts or []) if impact]

    if provider_id == "none":
        return {
            "provider": "none",
            "events": [],
            "warnings": ["Nessun provider calendario configurato: i filtri macro non vengono applicati."],
        }

    if provider_id == "manual":
        events = normalize_events(manual_events or _generate_demo_events(date_from, date_to, currencies))
        return {
            "provider": "manual",
            "events": _apply_event_filters(events, currencies, impacts),
            "warnings": ["Provider manual/demo: eventi utili per testare la logica news-safe, non per ricerca istituzionale."],
        }

    if provider_id == "trading_economics":
        api_key = (os.getenv("TRADING_ECONOMICS_API_KEY") or "").strip()
        if not api_key:
            return {
                "provider": "trading_economics",
                "events": [],
                "warnings": ["TRADING_ECONOMICS_API_KEY non configurata: filtri macro disattivati."],
            }
        url = "https://api.tradingeconomics.com/calendar"
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.get(url, params={"c": api_key})
            response.raise_for_status()
            raw = response.json()
        events = normalize_events(raw)
        ranged = [
            event
            for event in events
            if date_from <= event["timestamp"][:10] <= date_to
        ]
        return {
            "provider": "trading_economics",
            "events": _apply_event_filters(ranged, currencies, impacts),
            "warnings": [] if ranged else ["Il provider Trading Economics non ha restituito eventi nel range richiesto."],
        }

    unsupported = provider_status(provider_id)
    if unsupported and provider_id in {"forexfactory", "bloomberg", "morningstar", "investing", "fxstreet"}:
        return {
            "provider": provider_id,
            "events": [],
            "warnings": [
                f"Il provider {unsupported.get('name')} è visibile in UI ma non è interrogabile automaticamente in questa build.",
                unsupported.get("description") or "Provider non ancora integrato.",
            ],
        }

    return {
        "provider": provider_id,
        "events": [],
        "warnings": ["Provider calendario non riconosciuto."],
    }


def normalize_events(raw_events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized = []
    for item in raw_events or []:
        if not isinstance(item, dict):
            continue
        timestamp = _normalize_timestamp(
            item.get("date")
            or item.get("Date")
            or item.get("timestamp")
            or item.get("datetime")
        )
        if not timestamp:
            continue
        impact = _normalize_impact(item.get("impact") or item.get("Importance") or item.get("importance"))
        currency = _normalize_currency(item.get("currency") or item.get("Currency"))
        event_name = (
            item.get("event")
            or item.get("Event")
            or item.get("category")
            or item.get("Category")
            or "Economic Event"
        )
        normalized.append(
            {
                "event": str(event_name),
                "currency": currency,
                "impact": impact,
                "timestamp": timestamp,
                "actual": item.get("actual") or item.get("Actual"),
                "forecast": item.get("forecast") or item.get("Forecast"),
                "previous": item.get("previous") or item.get("Previous"),
                "source": item.get("source") or item.get("Source") or "provider",
            }
        )
    return sorted(normalized, key=lambda item: item["timestamp"])


def build_news_windows(
    events: list[dict[str, Any]],
    *,
    blackout_before_min: int,
    blackout_after_min: int,
) -> list[dict[str, Any]]:
    windows = []
    for event in events:
        try:
            ts = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        except Exception:
            continue
        windows.append(
            {
                "start": (ts - timedelta(minutes=max(0, blackout_before_min))).isoformat(),
                "end": (ts + timedelta(minutes=max(0, blackout_after_min))).isoformat(),
                "event": event.get("event"),
                "currency": event.get("currency"),
                "impact": event.get("impact"),
            }
        )
    return windows


def _generate_demo_events(date_from: str, date_to: str, currencies: list[str]) -> list[dict[str, Any]]:
    start = datetime.fromisoformat(f"{date_from}T00:00:00+00:00")
    end = datetime.fromisoformat(f"{date_to}T00:00:00+00:00")
    currencies = currencies or ["USD"]
    events = []
    current = start
    month_offset = 0
    while current <= end and len(events) < 24:
        event_time = current.replace(day=min(12, _days_in_month(current.year, current.month)), hour=13, minute=30)
        events.append(
            {
                "event": "High Impact CPI",
                "currency": currencies[month_offset % len(currencies)],
                "impact": "high",
                "timestamp": event_time.astimezone(timezone.utc).isoformat(),
                "source": "manual_demo",
            }
        )
        month_offset += 1
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return events


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    this_month = datetime(year, month, 1)
    return (next_month - this_month).days


def _normalize_timestamp(value: Any) -> str | None:
    if not value:
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except ValueError:
                parsed = None
        if parsed is None:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _normalize_impact(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"3", "high", "red", "important"}:
        return "high"
    if raw in {"2", "medium", "orange"}:
        return "medium"
    if raw in {"1", "low", "yellow"}:
        return "low"
    return "unknown"


def _normalize_currency(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if len(raw) == 3:
        return raw
    if "US" in raw or "DOLLAR" in raw:
        return "USD"
    if "EURO" in raw:
        return "EUR"
    if "POUND" in raw or "UK" in raw:
        return "GBP"
    return raw or "ALL"


def _apply_event_filters(events: list[dict[str, Any]], currencies: list[str], impacts: list[str]) -> list[dict[str, Any]]:
    filtered = []
    for event in events:
        if currencies and event.get("currency") not in currencies and event.get("currency") != "ALL":
            continue
        if impacts and event.get("impact") not in impacts:
            continue
        filtered.append(event)
    return filtered
