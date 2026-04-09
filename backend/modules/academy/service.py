from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from modules.academy.catalog import get_academy_catalog
from modules.academy.store import AcademyStore


MODULE_START_BY_LEVEL = {
    "beginner": "algo-foundations",
    "intermediate": "strategy-core",
    "advanced": "execution-microstructure",
}

STARTER_UNLOCK_COUNT = {
    "beginner": 2,
    "intermediate": 5,
    "advanced": 99,
}


def _normalize_level(value: Optional[str]) -> str:
    raw = (value or "").strip().lower()
    if raw in {"principiante", "base", "inizio", "iniziante", "beginner"}:
        return "beginner"
    if raw in {"intermedio", "intermediate", "mid"}:
        return "intermediate"
    if raw in {"avanzato", "advanced", "pro"}:
        return "advanced"
    return raw or "beginner"


def _parse_dt(value: Optional[str]) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _score_text(text: str, keywords: List[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword in lowered)


class AcademyService:
    @classmethod
    def _detect_level(cls, level_input: Optional[str], freeform_background: Optional[str]) -> str:
        normalized = _normalize_level(level_input)
        if normalized in {"beginner", "intermediate", "advanced"}:
            return normalized

        text = f"{level_input or ''} {freeform_background or ''}".lower()
        beginner_score = _score_text(
            text,
            [
                "principiante",
                "inizio",
                "base",
                "zero",
                "mai",
                "non so",
                "prime armi",
            ],
        )
        advanced_score = _score_text(
            text,
            [
                "portfolio",
                "microstruttura",
                "microstructure",
                "walk-forward",
                "cointegration",
                "ml",
                "machine learning",
                "execution",
                "latency",
                "order flow",
                "regime",
                "feature engineering",
            ],
        )
        intermediate_score = _score_text(
            text,
            [
                "mt5",
                "mql5",
                "python",
                "backtest",
                "indicatori",
                "indicator",
                "ea",
                "expert advisor",
                "strategia",
            ],
        )

        if advanced_score >= max(beginner_score, intermediate_score) and advanced_score > 0:
            return "advanced"
        if intermediate_score >= max(beginner_score, advanced_score) and intermediate_score > 0:
            return "intermediate"
        return "beginner"

    @classmethod
    def _recommend_module(cls, level: str, freeform_background: Optional[str]) -> Tuple[str, str]:
        text = (freeform_background or "").lower()
        keyword_map = [
            ("python-essentials", "Hai citato Python o costruzione segnali: parti dal blocco pratico per creare bot e test rapidi.", ["python", "pandas", "numpy", "dataframe"]),
            ("indicator-library", "Il tuo focus sembra sui segnali: la libreria indicatori ti dà una base ampia ma operativa.", ["indicatore", "indicator", "segnale", "signal", "momentum", "trend"]),
            ("backtesting", "Hai menzionato validazione o test: conviene partire dal modulo di backtesting professionale.", ["backtest", "validazione", "walk-forward", "monte carlo"]),
            ("risk-management", "Il focus sembra rischio e drawdown: conviene partire dal modulo di risk management.", ["rischio", "risk", "drawdown", "sizing", "loss"]),
            ("live-deployment", "Hai già una logica e vuoi portarla in operatività: parti da deploy e live trading.", ["live", "deploy", "runtime", "monitor", "adapter"]),
            ("portfolio-construction", "Il tuo linguaggio è da gestione multi-strategy: inizia dal portfolio construction.", ["portfolio", "allocazione", "correlazione", "exposure"]),
        ]
        for module_id, reason, keywords in keyword_map:
            if any(keyword in text for keyword in keywords):
                return module_id, reason
        default = MODULE_START_BY_LEVEL.get(level, "algo-foundations")
        reasons = {
            "algo-foundations": "Percorso consigliato per partire da zero e costruire fondamenta solide prima di builder, backtest e live.",
            "strategy-core": "Hai già una base sufficiente: conviene partire dal design della strategia e dal suo ciclo di miglioramento.",
            "execution-microstructure": "Il tuo profilo sembra avanzato: puoi partire dalla parte più desk-oriented su execution, costi e qualità del fill.",
        }
        return default, reasons.get(default, "Percorso consigliato in base al tuo profilo.")

    @classmethod
    def _build_search_index(cls, catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for module in catalog["modules"]:
            results.append(
                {
                    "kind": "module",
                    "id": module["id"],
                    "module_id": module["id"],
                    "lesson_id": None,
                    "indicator_id": None,
                    "title": module["title"],
                    "subtitle": module.get("category", ""),
                    "snippet": module.get("description", ""),
                    "search_text": " ".join(
                        [module.get("title", ""), module.get("description", ""), " ".join(module.get("objectives", []))]
                    ).lower(),
                }
            )
            for lesson in module.get("lessons", []):
                results.append(
                    {
                        "kind": "lesson",
                        "id": lesson["id"],
                        "module_id": module["id"],
                        "lesson_id": lesson["id"],
                        "indicator_id": None,
                        "title": lesson["title"],
                        "subtitle": module["title"],
                        "snippet": lesson.get("summary", ""),
                        "search_text": " ".join(
                            [
                                lesson.get("title", ""),
                                lesson.get("summary", ""),
                                lesson.get("theory", ""),
                                " ".join(lesson.get("practical", [])),
                                " ".join(lesson.get("mistakes", [])),
                                lesson.get("case_study", ""),
                            ]
                        ).lower(),
                    }
                )
            for category in module.get("indicator_categories", []):
                for indicator in category.get("indicators", []):
                    results.append(
                        {
                            "kind": "indicator",
                            "id": indicator["id"],
                            "module_id": module["id"],
                            "lesson_id": None,
                            "indicator_id": indicator["id"],
                            "title": indicator["name"],
                            "subtitle": f'{module["title"]} · {category["title"]}',
                            "snippet": indicator.get("interpretation", ""),
                            "search_text": " ".join(
                                [
                                    category.get("title", ""),
                                    category.get("description", ""),
                                    indicator.get("name", ""),
                                    indicator.get("formula", ""),
                                    indicator.get("interpretation", ""),
                                    indicator.get("works_when", ""),
                                    indicator.get("fails_when", ""),
                                    indicator.get("strategy_use", ""),
                                    " ".join(indicator.get("common_mistakes", [])),
                                    indicator.get("example", ""),
                                ]
                            ).lower(),
                        }
                    )
        return results

    @classmethod
    def _enrich_catalog(
        cls,
        *,
        catalog: Dict[str, Any],
        profile: Optional[Dict[str, Any]],
        progress_rows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        progress_by_lesson = {row["lesson_id"]: row for row in progress_rows}
        modules = catalog["modules"]
        recommended_module_id = (profile or {}).get("recommended_module_id") or modules[0]["id"]
        last_viewed_module_id = (profile or {}).get("last_viewed_module_id")

        module_progress_meta: List[Dict[str, Any]] = []
        for module in modules:
            lessons = module.get("lessons", [])
            completed_lessons = sum(1 for lesson in lessons if (progress_by_lesson.get(lesson["id"]) or {}).get("completed"))
            last_viewed_at = max(
                (_parse_dt((progress_by_lesson.get(lesson["id"]) or {}).get("last_viewed_at")) for lesson in lessons),
                default=datetime.min,
            )
            module_progress_meta.append(
                {
                    "id": module["id"],
                    "total_lessons": len(lessons),
                    "completed_lessons": completed_lessons,
                    "progress_pct": round((completed_lessons / len(lessons)) * 100) if lessons else 0,
                    "last_viewed_at": last_viewed_at,
                    "has_progress": any(progress_by_lesson.get(lesson["id"]) for lesson in lessons),
                }
            )

        meta_by_id = {item["id"]: item for item in module_progress_meta}
        level = _normalize_level((profile or {}).get("detected_level"))
        recommended_index = next((idx for idx, module in enumerate(modules) if module["id"] == recommended_module_id), 0)
        last_viewed_index = next((idx for idx, module in enumerate(modules) if module["id"] == last_viewed_module_id), 0)
        unlock_until = max(STARTER_UNLOCK_COUNT.get(level, 2) - 1, recommended_index, last_viewed_index)

        for idx, module in enumerate(modules[:-1]):
            meta = meta_by_id[module["id"]]
            if meta["progress_pct"] >= 60 or meta["has_progress"]:
                unlock_until = max(unlock_until, idx + 1)

        enriched_modules: List[Dict[str, Any]] = []
        for idx, module in enumerate(modules):
            meta = meta_by_id[module["id"]]
            locked = not (idx <= unlock_until or meta["has_progress"])
            if meta["progress_pct"] >= 100 and meta["total_lessons"] > 0:
                status = "completed"
            elif locked:
                status = "locked"
            else:
                status = "in_progress"

            enriched_lessons = []
            for lesson in module.get("lessons", []):
                lesson_progress = progress_by_lesson.get(lesson["id"]) or {}
                enriched_lessons.append(
                    {
                        **lesson,
                        "completed": bool(lesson_progress.get("completed")),
                        "last_viewed_at": lesson_progress.get("last_viewed_at"),
                    }
                )

            enriched_modules.append(
                {
                    **module,
                    "locked": locked,
                    "status": status,
                    "progress_pct": meta["progress_pct"],
                    "completed_lessons": meta["completed_lessons"],
                    "total_lessons": meta["total_lessons"],
                    "last_viewed_at": meta["last_viewed_at"].isoformat() if meta["last_viewed_at"] != datetime.min else None,
                    "lessons": enriched_lessons,
                }
            )

        return {
            **catalog,
            "modules": enriched_modules,
        }

    @classmethod
    def _build_dashboard(
        cls,
        *,
        modules: List[Dict[str, Any]],
        profile: Optional[Dict[str, Any]],
        progress_rows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        total_lessons = sum(module["total_lessons"] for module in modules)
        completed_lessons = sum(module["completed_lessons"] for module in modules)
        total_progress_pct = round((completed_lessons / total_lessons) * 100) if total_lessons else 0

        lesson_lookup: Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]] = {}
        for module in modules:
            for lesson in module.get("lessons", []):
                lesson_lookup[lesson["id"]] = (module, lesson)

        latest_lessons = []
        for row in sorted(progress_rows, key=lambda item: _parse_dt(item.get("last_viewed_at")), reverse=True)[:6]:
            pair = lesson_lookup.get(row["lesson_id"])
            if not pair:
                continue
            module, lesson = pair
            latest_lessons.append(
                {
                    "module_id": module["id"],
                    "module_title": module["title"],
                    "lesson_id": lesson["id"],
                    "lesson_title": lesson["title"],
                    "last_viewed_at": row.get("last_viewed_at"),
                    "completed": bool(row.get("completed")),
                }
            )

        continue_from_here = None
        preferred_lesson_id = (profile or {}).get("last_viewed_lesson_id")
        if preferred_lesson_id and preferred_lesson_id in lesson_lookup:
            module, lesson = lesson_lookup[preferred_lesson_id]
            if not lesson.get("completed"):
                continue_from_here = {
                    "module_id": module["id"],
                    "module_title": module["title"],
                    "lesson_id": lesson["id"],
                    "lesson_title": lesson["title"],
                    "reason": "Riparti dall’ultima lezione aperta.",
                }

        if continue_from_here is None:
            for module in modules:
                if module["locked"]:
                    continue
                next_lesson = next((lesson for lesson in module["lessons"] if not lesson.get("completed")), None)
                if next_lesson:
                    continue_from_here = {
                        "module_id": module["id"],
                        "module_title": module["title"],
                        "lesson_id": next_lesson["id"],
                        "lesson_title": next_lesson["title"],
                        "reason": "Questo è il prossimo step utile nel percorso.",
                    }
                    break

        personalized_suggestion = {
            "module_id": (profile or {}).get("recommended_module_id"),
            "reason": (profile or {}).get("recommendation_reason") or "Percorso consigliato in base al livello selezionato.",
        }
        suggested_module = next((module for module in modules if module["id"] == personalized_suggestion["module_id"]), modules[0])
        personalized_suggestion["module_title"] = suggested_module["title"]

        return {
            "total_progress_pct": total_progress_pct,
            "completed_lessons": completed_lessons,
            "total_lessons": total_lessons,
            "modules": [
                {
                    "module_id": module["id"],
                    "title": module["title"],
                    "difficulty": module["difficulty"],
                    "progress_pct": module["progress_pct"],
                    "status": module["status"],
                    "locked": module["locked"],
                    "estimated_hours": module["estimated_hours"],
                }
                for module in modules
            ],
            "latest_lessons": latest_lessons,
            "continue_from_here": continue_from_here,
            "personalized_suggestion": personalized_suggestion,
        }

    @classmethod
    async def bootstrap(cls, username: str) -> Dict[str, Any]:
        catalog = get_academy_catalog()
        profile = await AcademyStore.get_profile(username)
        if not profile:
            detected_level = "beginner"
            recommended_module_id, recommendation_reason = cls._recommend_module(detected_level, "")
            profile = await AcademyStore.upsert_profile(
                username=username,
                detected_level=detected_level,
                recommended_module_id=recommended_module_id,
                recommendation_reason=recommendation_reason,
            )
        progress_rows = await AcademyStore.list_progress(username)
        enriched_catalog = cls._enrich_catalog(catalog=catalog, profile=profile, progress_rows=progress_rows)
        dashboard = cls._build_dashboard(
            modules=enriched_catalog["modules"],
            profile=profile,
            progress_rows=progress_rows,
        )
        return {
            "profile": profile,
            "dashboard": dashboard,
            "catalog": enriched_catalog,
        }

    @classmethod
    async def update_profile(
        cls,
        *,
        username: str,
        level_input: Optional[str] = None,
        freeform_background: Optional[str] = None,
    ) -> Dict[str, Any]:
        existing = await AcademyStore.get_profile(username) or {}
        detected_level = cls._detect_level(level_input or existing.get("level_input"), freeform_background or existing.get("freeform_background"))
        recommended_module_id, recommendation_reason = cls._recommend_module(detected_level, freeform_background or existing.get("freeform_background"))
        await AcademyStore.upsert_profile(
            username=username,
            level_input=level_input if level_input is not None else existing.get("level_input"),
            detected_level=detected_level,
            freeform_background=freeform_background if freeform_background is not None else existing.get("freeform_background"),
            recommended_module_id=recommended_module_id,
            recommendation_reason=recommendation_reason,
        )
        return await cls.bootstrap(username)

    @classmethod
    async def mark_lesson_viewed(cls, *, username: str, module_id: str, lesson_id: str) -> Dict[str, Any]:
        await AcademyStore.mark_lesson_viewed(username=username, module_id=module_id, lesson_id=lesson_id)
        await AcademyStore.upsert_profile(
            username=username,
            last_viewed_module_id=module_id,
            last_viewed_lesson_id=lesson_id,
        )
        return await cls.bootstrap(username)

    @classmethod
    async def set_lesson_completed(
        cls,
        *,
        username: str,
        module_id: str,
        lesson_id: str,
        completed: bool,
    ) -> Dict[str, Any]:
        await AcademyStore.set_lesson_completed(
            username=username,
            module_id=module_id,
            lesson_id=lesson_id,
            completed=completed,
        )
        await AcademyStore.upsert_profile(
            username=username,
            last_viewed_module_id=module_id,
            last_viewed_lesson_id=lesson_id,
        )
        return await cls.bootstrap(username)

    @classmethod
    async def search(cls, *, username: str, query: str) -> Dict[str, Any]:
        payload = await cls.bootstrap(username)
        normalized = query.strip().lower()
        if len(normalized) < 2:
            return {"query": query, "results": []}

        search_index = cls._build_search_index(payload["catalog"])
        ranked = []
        for item in search_index:
            text = item["search_text"]
            if normalized not in text:
                continue
            score = 0
            if item["title"].lower().startswith(normalized):
                score += 6
            if normalized in item["title"].lower():
                score += 4
            if normalized in item["subtitle"].lower():
                score += 2
            score += max(1, 3 - (text.find(normalized) // 80 if normalized in text else 3))
            ranked.append((score, item))

        ranked.sort(key=lambda pair: (-pair[0], pair[1]["title"]))
        results = [
            {
                "kind": item["kind"],
                "id": item["id"],
                "module_id": item["module_id"],
                "lesson_id": item["lesson_id"],
                "indicator_id": item["indicator_id"],
                "title": item["title"],
                "subtitle": item["subtitle"],
                "snippet": item["snippet"],
            }
            for _, item in ranked[:12]
        ]
        return {"query": query, "results": results}
