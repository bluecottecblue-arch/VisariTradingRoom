import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, Request


DEFAULT_SESSION_TTL_SECONDS = 60 * 60 * 24 * 14


@dataclass
class AuthContext:
    username: str
    role: str
    exp: int


def _get_session_secret() -> str:
    return os.environ.get("SESSION_SECRET", "dev-session-secret-change-me")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def create_session_token(username: str, role: str, ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": int(time.time()) + ttl_seconds,
    }
    encoded_payload = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = hmac.new(
        _get_session_secret().encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{encoded_payload}.{_b64url_encode(signature)}"


def verify_session_token(token: str) -> Optional[AuthContext]:
    if not token or "." not in token:
        return None

    payload_part, signature_part = token.split(".", 1)
    expected_signature = hmac.new(
        _get_session_secret().encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    try:
        provided_signature = _b64url_decode(signature_part)
    except Exception:
        return None

    if not hmac.compare_digest(expected_signature, provided_signature):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except Exception:
        return None

    exp = int(payload.get("exp") or 0)
    if exp <= int(time.time()):
        return None

    username = str(payload.get("sub") or "").strip()
    role = str(payload.get("role") or "").strip()
    if not username or role not in {"user", "admin"}:
        return None

    return AuthContext(username=username, role=role, exp=exp)


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return request.headers.get("x-session-token", "").strip()


def _is_expired(expires_at: Optional[str]) -> bool:
    if not expires_at:
        return False
    try:
        dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt <= datetime.now(timezone.utc)


async def require_authenticated(request: Request) -> AuthContext:
    token = _extract_bearer_token(request)
    context = verify_session_token(token)
    if not context:
        raise HTTPException(status_code=401, detail="Sessione non valida o scaduta")
    if context.role == "user":
        from modules.auth.user_store import get_user_profile

        profile = await get_user_profile(context.username)
        if not profile:
            raise HTTPException(status_code=401, detail="Sessione non valida o scaduta")
        status = str(profile.get("status") or "").strip().lower()
        if _is_expired(profile.get("expires_at")) or status == "expired":
            raise HTTPException(status_code=403, detail="Account scaduto")
        if status != "active":
            raise HTTPException(status_code=403, detail="Account sospeso o non attivo")
    return context


async def require_admin(request: Request) -> AuthContext:
    context = await require_authenticated(request)
    if context.role != "admin":
        raise HTTPException(status_code=403, detail="Accesso admin richiesto")
    return context


async def ensure_session_access(session_id: str, context: AuthContext) -> dict:
    from db.database import InMemorySessionStore
    from modules.projects.store import ProjectStore

    project_ref = InMemorySessionStore.get(session_id, "project_ref") or {}
    if context.role == "admin":
        return project_ref

    owner_username = str(project_ref.get("owner_username") or "").strip().lower()
    if owner_username:
        if owner_username != context.username:
            raise HTTPException(status_code=404, detail="Sessione non trovata o non accessibile")
        return project_ref

    project_id = str(project_ref.get("project_id") or "").strip()
    if not project_id:
        raise HTTPException(status_code=404, detail="Sessione non trovata o non accessibile")

    project = await ProjectStore.get_project(context.username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Sessione non trovata o non accessibile")

    updated_ref = {**project_ref, "project_id": project_id, "owner_username": context.username}
    InMemorySessionStore.save(session_id, "project_ref", updated_ref)
    return updated_ref
