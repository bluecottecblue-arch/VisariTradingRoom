import os

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from modules.auth.security import AuthContext, create_session_token, require_admin, require_authenticated
from modules.auth.user_store import create_user, delete_user, get_user_count, list_users, reset_password, verify_user


router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreateRequest(BaseModel):
    username: str
    password: str


class PasswordResetRequest(BaseModel):
    password: str


def _normalize_admin_username() -> str:
    return str(os.environ.get("ADMIN_USERNAME") or "").strip().lower()


def _validate_admin_credentials(username: str, password: str) -> bool:
    expected_username = _normalize_admin_username()
    expected_password = str(os.environ.get("ADMIN_PASSWORD") or "")
    return bool(expected_username and expected_password and username.strip().lower() == expected_username and password == expected_password)


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
    if not _normalize_admin_username() or not os.environ.get("ADMIN_PASSWORD"):
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
    return {
        "authenticated": True,
        "username": context.username,
        "role": context.role,
        "exp": context.exp,
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
        user = create_user(payload.username, payload.password)
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
