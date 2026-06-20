import os
import time
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel

from modules.auth.security import AuthContext, create_session_token, require_admin, require_authenticated
from modules.auth.user_store import (
    create_user,
    delete_user,
    get_user_count,
    get_user_profile,
    list_users,
    reset_password,
    update_user,
    verify_user,
)


router = APIRouter()
_FAILED_LOGIN_ATTEMPTS: dict[str, dict[str, float]] = {}
_LOGIN_WINDOW_SECONDS = 10 * 60
_LOGIN_MAX_ATTEMPTS = 8


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreateRequest(BaseModel):
    username: str
    password: str
    status: str = "active"
    plan: str = "standard"
    expires_at: Optional[str] = None
    notes: Optional[str] = None
    ai_provider: str = "anthropic"
    claude_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None


class PasswordResetRequest(BaseModel):
    password: str


class UserUpdateRequest(BaseModel):
    status: Optional[str] = None
    plan: Optional[str] = None
    expires_at: Optional[str] = None
    notes: Optional[str] = None
    ai_provider: Optional[str] = None
    claude_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    polygon_api_key: Optional[str] = None
    twelvedata_api_key: Optional[str] = None
    alphavantage_api_key: Optional[str] = None


def _normalize_admin_username() -> str:
    return str(os.environ.get("ADMIN_USERNAME") or "").strip().lower()


def _normalize_admin_password() -> str:
    return str(os.environ.get("ADMIN_PASSWORD") or "").strip()


def _validate_admin_credentials(username: str, password: str) -> bool:
    expected_username = _normalize_admin_username()
    expected_password = _normalize_admin_password()
    return bool(
        expected_username
        and expected_password
        and username.strip().lower() == expected_username
        and password.strip() == expected_password
    )


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def _rate_limit_key(request: Request, username: str, scope: str) -> str:
    return f"{scope}:{_client_ip(request)}:{username.strip().lower()}"


def _check_rate_limit(key: str) -> None:
    now = time.time()
    stale_keys = [item for item, record in _FAILED_LOGIN_ATTEMPTS.items() if record.get("reset_at", 0) <= now]
    for stale_key in stale_keys:
        _FAILED_LOGIN_ATTEMPTS.pop(stale_key, None)
    record = _FAILED_LOGIN_ATTEMPTS.get(key)
    if record and record.get("count", 0) >= _LOGIN_MAX_ATTEMPTS and record.get("reset_at", 0) > now:
        wait_seconds = max(1, int(record["reset_at"] - now))
        raise HTTPException(
            status_code=429,
            detail=f"Troppi tentativi di login falliti. Riprova tra circa {wait_seconds} secondi.",
        )


def _register_failed_attempt(key: str) -> None:
    now = time.time()
    record = _FAILED_LOGIN_ATTEMPTS.get(key)
    if not record or record.get("reset_at", 0) <= now:
        _FAILED_LOGIN_ATTEMPTS[key] = {"count": 1, "reset_at": now + _LOGIN_WINDOW_SECONDS}
        return
    record["count"] = record.get("count", 0) + 1


def _clear_failed_attempts(key: str) -> None:
    _FAILED_LOGIN_ATTEMPTS.pop(key, None)


@router.post("/login")
async def login_user(payload: LoginRequest, request: Request):
    rate_limit_key = _rate_limit_key(request, payload.username, "user_login")
    _check_rate_limit(rate_limit_key)
    user = await verify_user(payload.username, payload.password)
    if not user:
        _register_failed_attempt(rate_limit_key)
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    _clear_failed_attempts(rate_limit_key)

    return {
        "ok": True,
        "username": user["username"],
        "role": "user",
        "token": create_session_token(user["username"], "user"),
    }


@router.post("/admin/login")
async def login_admin(payload: LoginRequest, request: Request):
    rate_limit_key = _rate_limit_key(request, payload.username, "admin_login")
    _check_rate_limit(rate_limit_key)
    if not _normalize_admin_username() or not _normalize_admin_password():
        raise HTTPException(status_code=503, detail="Admin non configurato")
    if not _validate_admin_credentials(payload.username, payload.password):
        _register_failed_attempt(rate_limit_key)
        raise HTTPException(status_code=401, detail="Credenziali admin non valide")
    _clear_failed_attempts(rate_limit_key)

    return {
        "ok": True,
        "username": _normalize_admin_username(),
        "role": "admin",
        "token": create_session_token(_normalize_admin_username(), "admin"),
    }


@router.get("/me")
async def get_current_user(context: AuthContext = Depends(require_authenticated)):
    user_profile = await get_user_profile(context.username) if context.role == "user" else None
    return {
        "authenticated": True,
        "username": context.username,
        "role": context.role,
        "exp": context.exp,
        "ai_provider": (user_profile or {}).get("ai_provider", "anthropic"),
        "claude_key_configured": bool((user_profile or {}).get("claude_key_configured")),
        "openai_key_configured": bool((user_profile or {}).get("openai_key_configured")),
        "google_key_configured": bool((user_profile or {}).get("google_key_configured")),
        "plan": (user_profile or {}).get("plan"),
        "status": (user_profile or {}).get("status"),
        "expires_at": (user_profile or {}).get("expires_at"),
    }


@router.get("/admin/users")
async def admin_list_users(context: AuthContext = Depends(require_admin)):
    return {
        "ok": True,
        "admin": context.username,
        "total": await get_user_count(),
        "users": await list_users(),
    }


@router.post("/admin/users")
async def admin_create_user(
    payload: UserCreateRequest,
    context: AuthContext = Depends(require_admin),
):
    try:
        user = await create_user(
            payload.username,
            payload.password,
            status=payload.status,
            plan=payload.plan,
            expires_at=payload.expires_at,
            notes=payload.notes or "",
            ai_provider=payload.ai_provider,
            claude_api_key=payload.claude_api_key,
            openai_api_key=payload.openai_api_key,
            google_api_key=payload.google_api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "admin": context.username,
        "user": user,
    }


@router.post("/admin/users/{username}/reset-password")
async def admin_reset_password(
    username: str,
    payload: PasswordResetRequest = Body(...),
    context: AuthContext = Depends(require_admin),
):
    try:
        updated = await reset_password(username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "admin": context.username,
        "user": updated,
    }


@router.patch("/admin/users/{username}")
async def admin_update_user(
    username: str,
    payload: UserUpdateRequest = Body(...),
    context: AuthContext = Depends(require_admin),
):
    if username.strip().lower() == _normalize_admin_username():
        raise HTTPException(status_code=400, detail="L'account admin env non è gestibile da qui")
    try:
        updated = await update_user(
            username,
            status=payload.status,
            plan=payload.plan,
            expires_at=payload.expires_at,
            notes=payload.notes,
            ai_provider=payload.ai_provider,
            claude_api_key=payload.claude_api_key,
            openai_api_key=payload.openai_api_key,
            google_api_key=payload.google_api_key,
            polygon_api_key=payload.polygon_api_key,
            twelvedata_api_key=payload.twelvedata_api_key,
            alphavantage_api_key=payload.alphavantage_api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "admin": context.username,
        "user": updated,
    }


@router.delete("/admin/users/{username}")
async def admin_delete_user(username: str, context: AuthContext = Depends(require_admin)):
    if username.strip().lower() == _normalize_admin_username():
        raise HTTPException(status_code=400, detail="L'account admin env non può essere cancellato da qui")

    removed = await delete_user(username)
    if not removed:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    return {
        "ok": True,
        "admin": context.username,
        "deleted": username.strip().lower(),
    }
