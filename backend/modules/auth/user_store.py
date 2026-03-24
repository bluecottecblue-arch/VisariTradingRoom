import json
import os
import secrets
import threading
from datetime import datetime, timezone
from hashlib import pbkdf2_hmac
from pathlib import Path
from typing import Optional


_LOCK = threading.Lock()
_PBKDF2_ROUNDS = 120_000
_VALID_USER_STATUSES = {"active", "suspended", "expired"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _storage_path() -> Path:
    raw = os.environ.get("USERS_STORAGE_PATH")
    if raw:
        path = Path(raw)
    else:
        storage_root = Path(os.environ.get("STORAGE_PATH", "./storage"))
        path = storage_root / "users.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _ensure_file() -> Path:
    path = _storage_path()
    if not path.exists():
        path.write_text(json.dumps({"users": []}, indent=2), encoding="utf-8")
    return path


def _read_data() -> dict:
    path = _ensure_file()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        payload = {"users": []}
    if not isinstance(payload, dict):
        payload = {"users": []}
    payload.setdefault("users", [])
    if not isinstance(payload["users"], list):
        payload["users"] = []
    for user in payload["users"]:
        if not isinstance(user, dict):
            continue
        user.setdefault("status", "active")
        user.setdefault("plan", "standard")
        user.setdefault("expires_at", None)
        user.setdefault("notes", "")
        user.setdefault("claude_api_key", "")
    return payload


def _write_data(payload: dict) -> None:
    path = _ensure_file()
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _normalize_username(username: str) -> str:
    return str(username or "").strip().lower()


def _hash_password(password: str, salt: str) -> str:
    digest = pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        _PBKDF2_ROUNDS,
    )
    return digest.hex()


def _build_password_record(password: str) -> dict:
    salt = secrets.token_hex(16)
    return {
        "salt": salt,
        "hash": _hash_password(password, salt),
        "rounds": _PBKDF2_ROUNDS,
    }


def _find_user(payload: dict, username: str) -> Optional[dict]:
    normalized = _normalize_username(username)
    for user in payload.get("users", []):
        if _normalize_username(user.get("username")) == normalized:
            return user
    return None


def _normalize_status(status: Optional[str]) -> str:
    value = str(status or "active").strip().lower()
    return value if value in _VALID_USER_STATUSES else "active"


def _normalize_plan(plan: Optional[str]) -> str:
    value = str(plan or "standard").strip().lower()
    return value or "standard"


def _normalize_expires_at(raw: Optional[str]) -> Optional[str]:
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError as exc:
        raise ValueError("expires_at non valido: usa ISO date/time") from exc


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


def list_users() -> list[dict]:
    with _LOCK:
        payload = _read_data()
        users = []
        for user in payload.get("users", []):
            effective_status = "expired" if _is_expired(user.get("expires_at")) else _normalize_status(user.get("status"))
            users.append(
                {
                    "username": user.get("username"),
                    "status": effective_status,
                    "plan": user.get("plan") or "standard",
                    "expires_at": user.get("expires_at"),
                    "notes": user.get("notes") or "",
                    "claude_key_configured": bool(str(user.get("claude_api_key") or "").strip()),
                    "created_at": user.get("created_at"),
                    "updated_at": user.get("updated_at"),
                    "last_login_at": user.get("last_login_at"),
                }
            )
        return sorted(users, key=lambda item: item.get("username") or "")


def create_user(
    username: str,
    password: str,
    *,
    status: str = "active",
    plan: str = "standard",
    expires_at: Optional[str] = None,
    notes: str = "",
    claude_api_key: Optional[str] = None,
) -> dict:
    normalized = _normalize_username(username)
    if len(normalized) < 3:
        raise ValueError("Username troppo corto")
    if len(password or "") < 6:
        raise ValueError("Password troppo corta: minimo 6 caratteri")

    with _LOCK:
        payload = _read_data()
        if _find_user(payload, normalized):
            raise ValueError("Username già esistente")

        now = _utc_now()
        user = {
            "username": normalized,
            "password": _build_password_record(password),
            "status": _normalize_status(status),
            "plan": _normalize_plan(plan),
            "expires_at": _normalize_expires_at(expires_at),
            "notes": str(notes or "").strip(),
            "claude_api_key": str(claude_api_key or "").strip(),
            "created_at": now,
            "updated_at": now,
            "last_login_at": None,
        }
        payload["users"].append(user)
        _write_data(payload)
        return {
            "username": normalized,
            "status": user["status"],
            "plan": user["plan"],
            "expires_at": user["expires_at"],
            "notes": user["notes"],
            "claude_key_configured": bool(user["claude_api_key"]),
            "created_at": now,
            "updated_at": now,
            "last_login_at": None,
        }


def delete_user(username: str) -> bool:
    normalized = _normalize_username(username)
    with _LOCK:
        payload = _read_data()
        before = len(payload.get("users", []))
        payload["users"] = [
            user
            for user in payload.get("users", [])
            if _normalize_username(user.get("username")) != normalized
        ]
        removed = len(payload["users"]) != before
        if removed:
            _write_data(payload)
        return removed


def reset_password(username: str, password: str) -> dict:
    normalized = _normalize_username(username)
    if len(password or "") < 6:
        raise ValueError("Password troppo corta: minimo 6 caratteri")

    with _LOCK:
        payload = _read_data()
        user = _find_user(payload, normalized)
        if not user:
            raise ValueError("Utente non trovato")
        user["password"] = _build_password_record(password)
        user["updated_at"] = _utc_now()
        _write_data(payload)
        return {
            "username": user.get("username"),
            "status": user.get("status", "active"),
            "updated_at": user.get("updated_at"),
        }


def update_user(
    username: str,
    *,
    status: Optional[str] = None,
    plan: Optional[str] = None,
    expires_at: Optional[str] = None,
    notes: Optional[str] = None,
    claude_api_key: Optional[str] = None,
) -> dict:
    normalized = _normalize_username(username)
    with _LOCK:
        payload = _read_data()
        user = _find_user(payload, normalized)
        if not user:
            raise ValueError("Utente non trovato")
        if status is not None:
            user["status"] = _normalize_status(status)
        if plan is not None:
            user["plan"] = _normalize_plan(plan)
        if expires_at is not None:
            user["expires_at"] = _normalize_expires_at(expires_at)
        if notes is not None:
            user["notes"] = str(notes).strip()
        if claude_api_key is not None:
            user["claude_api_key"] = str(claude_api_key).strip()
        if _is_expired(user.get("expires_at")):
            user["status"] = "expired"
        user["updated_at"] = _utc_now()
        _write_data(payload)
        return {
            "username": user.get("username"),
            "status": user.get("status", "active"),
            "plan": user.get("plan", "standard"),
            "expires_at": user.get("expires_at"),
            "notes": user.get("notes", ""),
            "claude_key_configured": bool(str(user.get("claude_api_key") or "").strip()),
            "updated_at": user.get("updated_at"),
        }


def verify_user(username: str, password: str) -> Optional[dict]:
    normalized = _normalize_username(username)
    with _LOCK:
        payload = _read_data()
        user = _find_user(payload, normalized)
        if not user:
            return None

        password_record = user.get("password") or {}
        salt = str(password_record.get("salt") or "")
        stored_hash = str(password_record.get("hash") or "")
        if not salt or not stored_hash:
            return None
        if _is_expired(user.get("expires_at")):
            user["status"] = "expired"
            user["updated_at"] = _utc_now()
            _write_data(payload)
            return None
        if _normalize_status(user.get("status")) != "active":
            return None

        candidate_hash = _hash_password(password, salt)
        if not secrets.compare_digest(candidate_hash, stored_hash):
            return None

        user["last_login_at"] = _utc_now()
        _write_data(payload)
        return {
            "username": user.get("username"),
            "status": user.get("status", "active"),
            "plan": user.get("plan", "standard"),
            "expires_at": user.get("expires_at"),
            "claude_key_configured": bool(str(user.get("claude_api_key") or "").strip()),
            "created_at": user.get("created_at"),
            "updated_at": user.get("updated_at"),
            "last_login_at": user.get("last_login_at"),
        }


def get_user_count() -> int:
    with _LOCK:
        payload = _read_data()
        return len(payload.get("users", []))


def get_user_profile(username: str) -> Optional[dict]:
    normalized = _normalize_username(username)
    with _LOCK:
        payload = _read_data()
        user = _find_user(payload, normalized)
        if not user:
            return None
        effective_status = "expired" if _is_expired(user.get("expires_at")) else _normalize_status(user.get("status"))
        return {
            "username": user.get("username"),
            "status": effective_status,
            "plan": user.get("plan", "standard"),
            "expires_at": user.get("expires_at"),
            "notes": user.get("notes") or "",
            "claude_key_configured": bool(str(user.get("claude_api_key") or "").strip()),
            "created_at": user.get("created_at"),
            "updated_at": user.get("updated_at"),
            "last_login_at": user.get("last_login_at"),
        }


def get_user_claude_api_key(username: str) -> str:
    normalized = _normalize_username(username)
    with _LOCK:
        payload = _read_data()
        user = _find_user(payload, normalized)
        if not user:
            return ""
        return str(user.get("claude_api_key") or "").strip()
