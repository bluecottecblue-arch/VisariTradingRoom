import os
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
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


@router.post("/login")
async def login_user(payload: LoginRequest):
    user = verify_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Credenziali non valide")

    return {
        "ok": True,
        "username": user["username"],
        "role": "user",
        "token": create_session_token(user["username"], "user"),
    }


@router.post("/admin/login")
async def login_admin(payload: LoginRequest):
    if not _normalize_admin_username() or not _normalize_admin_password():
        raise HTTPException(status_code=503, detail="Admin non configurato")
    if not _validate_admin_credentials(payload.username, payload.password):
        raise HTTPException(status_code=401, detail="Credenziali admin non valide")

    return {
        "ok": True,
        "username": _normalize_admin_username(),
        "role": "admin",
        "token": create_session_token(_normalize_admin_username(), "admin"),
    }


@router.get("/me")
async def get_current_user(context: AuthContext = Depends(require_authenticated)):
    user_profile = get_user_profile(context.username) if context.role == "user" else None
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
        "total": get_user_count(),
        "users": list_users(),
    }


@router.post("/admin/users")
async def admin_create_user(
    payload: UserCreateRequest,
    context: AuthContext = Depends(require_admin),
):
    try:
        user = create_user(
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
        updated = reset_password(username, payload.password)
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
        updated = update_user(
            username,
            status=payload.status,
            plan=payload.plan,
            expires_at=payload.expires_at,
            notes=payload.notes,
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
        "user": updated,
    }


@router.delete("/admin/users/{username}")
async def admin_delete_user(username: str, context: AuthContext = Depends(require_admin)):
    if username.strip().lower() == _normalize_admin_username():
        raise HTTPException(status_code=400, detail="L'account admin env non può essere cancellato da qui")

    removed = delete_user(username)
    if not removed:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    return {
        "ok": True,
        "admin": context.username,
        "deleted": username.strip().lower(),
    }
