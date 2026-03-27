from __future__ import annotations


def build_public_error(stage_label: str, exc: Exception) -> str:
    raw = str(exc or "").strip()
    lowered = raw.lower()

    if "credit balance is too low" in lowered or ("credit" in lowered and ("insufficient" in lowered or "too low" in lowered)):
        return f"{stage_label} non disponibile: credito provider insufficiente."

    if (
        "api key" in lowered
        or "authentication" in lowered
        or "unauthorized" in lowered
        or "forbidden" in lowered
        or "invalid api" in lowered
        or "invalid x-api-key" in lowered
        or "missing api key" in lowered
    ):
        return f"{stage_label} non disponibile: credenziali provider mancanti o non valide."

    if (
        "timeout" in lowered
        or "timed out" in lowered
        or "temporarily unavailable" in lowered
        or "overloaded" in lowered
        or "rate limit" in lowered
        or "429" in lowered
        or "529" in lowered
        or "connection reset" in lowered
    ):
        return f"{stage_label} temporaneamente non disponibile. Riprova tra qualche minuto."

    return f"{stage_label} non completato per un errore interno. Riprova."
