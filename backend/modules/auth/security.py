import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
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


def require_authenticated(request: Request) -> AuthContext:
    token = _extract_bearer_token(request)
    context = verify_session_token(token)
    if not context:
        raise HTTPException(status_code=401, detail="Sessione non valida o scaduta")
    return context


def require_admin(request: Request) -> AuthContext:
    context = require_authenticated(request)
    if context.role != "admin":
        raise HTTPException(status_code=403, detail="Accesso admin richiesto")
    return context
