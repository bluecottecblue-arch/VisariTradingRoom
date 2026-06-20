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
        path = resolve_storage_path("users.json")
    if not path.is_absolute():
        path = resolve_storage_path(str(path))
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
        user.setdefault("ai_provider", "anthropic")
        user.setdefault("claude_api_key", "")
        user.setdefault("openai_api_key", "")
        user.setdefault("google_api_key", "")
        user.setdefault("email", None)
        user.setdefault("stripe_customer_id", None)
        user.setdefault("stripe_subscription_id", None)
        user.setdefault("subscription_status", "none")
        user.setdefault("referral_code", None)
        user.setdefault("referred_by", None)
        user.setdefault("free_months_credit", 0)
        user.setdefault("referral_count", 0)
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


def _normalize_ai_provider(value: Optional[str]) -> str:
    provider = str(value or "anthropic").strip().lower()
    return provider if provider in {"anthropic", "openai", "google"} else "anthropic"


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


def _legacy_user_to_public_dict(user: dict) -> dict:
    return {
        "username": user.get("username"),
        "email": user.get("email"),
        "status": _normalize_status(user.get("status")),
        "plan": _normalize_plan(user.get("plan")),
        "expires_at": user.get("expires_at"),
        "notes": str(user.get("notes") or "").strip(),
        "ai_provider": _normalize_ai_provider(user.get("ai_provider")),
        "claude_key_configured": bool(str(user.get("claude_api_key") or "").strip()),
        "openai_key_configured": bool(str(user.get("openai_api_key") or "").strip()),
        "google_key_configured": bool(str(user.get("google_api_key") or "").strip()),
        "subscription_status": str(user.get("subscription_status") or "none"),
        "referral_code": user.get("referral_code"),
        "referred_by": user.get("referred_by"),
        "free_months_credit": int(user.get("free_months_credit") or 0),
        "referral_count": int(user.get("referral_count") or 0),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at"),
        "last_login_at": user.get("last_login_at"),
    }


def _legacy_verify_password(user: dict, password: str) -> bool:
    password_data = user.get("password") or {}
    salt = password_data.get("salt")
    digest = password_data.get("hash")
    if not salt or not digest:
        return False
    candidate_hash = _hash_password(password, salt)
    return secrets.compare_digest(candidate_hash, digest)


from sqlalchemy import select, delete, func
from db.database import is_db_available, AsyncSessionLocal, resolve_storage_path
from db.models import User as DBUser


def _user_to_dict(user: DBUser) -> dict:
    return {
        "username": user.username,
        "email": getattr(user, "email", None),
        "status": user.status,
        "plan": user.plan,
        "expires_at": user.expires_at.isoformat() if user.expires_at else None,
        "notes": user.notes or "",
        "ai_provider": user.ai_provider,
        "claude_key_configured": bool(user.claude_api_key),
        "openai_key_configured": bool(user.openai_api_key),
        "google_key_configured": bool(user.google_api_key),
        "subscription_status": getattr(user, "subscription_status", None) or "none",
        "referral_code": getattr(user, "referral_code", None),
        "referred_by": getattr(user, "referred_by", None),
        "free_months_credit": int(getattr(user, "free_months_credit", 0) or 0),
        "referral_count": int(getattr(user, "referral_count", 0) or 0),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


def _db_user_to_legacy_dict(user: DBUser) -> dict:
    return {
        "username": user.username,
        "password": {
            "salt": user.password_salt,
            "hash": user.password_hash,
            "rounds": _PBKDF2_ROUNDS,
        },
        "status": user.status,
        "plan": user.plan,
        "expires_at": user.expires_at.isoformat() if user.expires_at else None,
        "notes": user.notes or "",
        "ai_provider": _normalize_ai_provider(user.ai_provider),
        "claude_api_key": user.claude_api_key or "",
        "openai_api_key": user.openai_api_key or "",
        "google_api_key": user.google_api_key or "",
        "email": getattr(user, "email", None),
        "stripe_customer_id": getattr(user, "stripe_customer_id", None),
        "stripe_subscription_id": getattr(user, "stripe_subscription_id", None),
        "subscription_status": getattr(user, "subscription_status", None) or "none",
        "referral_code": getattr(user, "referral_code", None),
        "referred_by": getattr(user, "referred_by", None),
        "free_months_credit": int(getattr(user, "free_months_credit", 0) or 0),
        "referral_count": int(getattr(user, "referral_count", 0) or 0),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


async def _sync_db_users_backup(session=None) -> None:
    if not is_db_available():
        return

    owns_session = session is None
    if owns_session:
        async with AsyncSessionLocal() as owned_session:
            await _sync_db_users_backup(owned_session)
        return

    result = await session.execute(select(DBUser).order_by(DBUser.username))
    users = result.scalars().all()
    payload = {"users": [_db_user_to_legacy_dict(user) for user in users]}
    with _LOCK:
        _write_data(payload)


async def migrate_legacy_users():
    """Migra gli utenti dal vecchio users.json al nuovo database SQLite/Postgres."""
    # Se il DB non è pronto, non possiamo migrare
    if not is_db_available():
        return

    path = _storage_path()
    if not path.exists():
        return

    print(f"📦 Trovato archivio legacy {path.name}. Controllo migrazione...")
    
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        legacy_users = payload.get("users", [])
        if not legacy_users:
            return
    except Exception as e:
        print(f"⚠️  Errore lettura {path.name}: {e}")
        return

    async with AsyncSessionLocal() as session:
        # Conta quanti utenti ci sono già nel DB
        count_res = await session.execute(select(func.count(DBUser.username)))
        db_count = count_res.scalar() or 0
        
        # Se il DB è già popolato, assumiamo che la migrazione sia già avvenuta
        # o che l'utente voglia un DB pulito. In produzione, di solito si migra solo se il DB è vuoto.
        if db_count > 0:
            print(f"ℹ️  Database già popolato ({db_count} utenti). Salto migrazione legacy.")
            return

        print(f"🚛 Migrazione di {len(legacy_users)} utenti in corso...")
        count = 0
        for lu in legacy_users:
            try:
                username = _normalize_username(lu.get("username"))
                if not username:
                    continue
                
                # Password record
                password_data = lu.get("password") or {}
                
                user = DBUser(
                    username=username,
                    password_hash=password_data.get("hash"),
                    password_salt=password_data.get("salt"),
                    status=_normalize_status(lu.get("status")),
                    plan=_normalize_plan(lu.get("plan")),
                    expires_at=datetime.fromisoformat(lu["expires_at"].replace("Z", "+00:00")) if lu.get("expires_at") else None,
                    notes=str(lu.get("notes") or "").strip(),
                    ai_provider=str(lu.get("ai_provider") or "anthropic").strip(),
                    claude_api_key=str(lu.get("claude_api_key") or "").strip(),
                    openai_api_key=str(lu.get("openai_api_key") or "").strip(),
                    google_api_key=str(lu.get("google_api_key") or "").strip(),
                    created_at=datetime.fromisoformat(lu["created_at"].replace("Z", "+00:00")) if lu.get("created_at") else datetime.now(timezone.utc),
                    updated_at=datetime.fromisoformat(lu["updated_at"].replace("Z", "+00:00")) if lu.get("updated_at") else datetime.now(timezone.utc),
                    last_login_at=datetime.fromisoformat(lu["last_login_at"].replace("Z", "+00:00")) if lu.get("last_login_at") else None,
                )
                session.add(user)
                count += 1
            except Exception as ee:
                print(f"⚠️  Salto utente {lu.get('username')}: {ee}")

        await session.commit()
        print(f"✅ Migrazione completata: {count} utenti importati.")
        
        # Rinominiamo il file vecchio per evitare di riprocessarlo
        try:
            old_name = path.with_suffix(".json.migrated")
            path.rename(old_name)
            print(f"♻️  File legacy rinominato in {old_name.name}")
        except Exception:
            pass


async def list_users() -> list[dict]:
    if not is_db_available():
        with _LOCK:
            payload = _read_data()
            return [_legacy_user_to_public_dict(user) for user in payload.get("users", [])]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(DBUser).order_by(DBUser.username))
        return [_user_to_dict(u) for u in result.scalars().all()]
    return []


async def create_user(
    username: str,
    password: str,
    *,
    status: str = "active",
    plan: str = "standard",
    expires_at: Optional[str] = None,
    notes: str = "",
    ai_provider: str = "anthropic",
    claude_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    google_api_key: Optional[str] = None,
) -> dict:
    normalized = _normalize_username(username)
    if len(normalized) < 3:
        raise ValueError("Username troppo corto")
    if len(password or "") < 6:
        raise ValueError("Password troppo corta: minimo 6 caratteri")

    if not is_db_available():
        with _LOCK:
            payload = _read_data()
            existing = _find_user(payload, normalized)
            if existing:
                raise ValueError("Username già esistente")
            legacy_user = {
                "username": normalized,
                "password": _build_password_record(password),
                "status": _normalize_status(status),
                "plan": _normalize_plan(plan),
                "expires_at": _normalize_expires_at(expires_at),
                "notes": str(notes or "").strip(),
                "ai_provider": _normalize_ai_provider(ai_provider),
                "claude_api_key": str(claude_api_key or "").strip(),
                "openai_api_key": str(openai_api_key or "").strip(),
                "google_api_key": str(google_api_key or "").strip(),
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
                "last_login_at": None,
            }
            payload.setdefault("users", []).append(legacy_user)
            payload["users"].sort(key=lambda item: str(item.get("username") or ""))
            _write_data(payload)
            return _legacy_user_to_public_dict(legacy_user)

    pwd_rec = _build_password_record(password)

    async with AsyncSessionLocal() as session:
        existing = await session.get(DBUser, normalized)
        if existing:
            raise ValueError("Username già esistente")
        
        user = DBUser(
            username=normalized,
            password_hash=pwd_rec["hash"],
            password_salt=pwd_rec["salt"],
            status=_normalize_status(status),
            plan=_normalize_plan(plan),
            expires_at=datetime.fromisoformat(expires_at.replace("Z", "+00:00")) if expires_at else None,
            notes=str(notes or "").strip(),
            ai_provider=str(ai_provider or "anthropic").strip(),
            claude_api_key=str(claude_api_key or "").strip(),
            openai_api_key=str(openai_api_key or "").strip(),
            google_api_key=str(google_api_key or "").strip(),
        )
        session.add(user)
        await session.commit()
        await _sync_db_users_backup(session)
        await session.refresh(user)
        return _user_to_dict(user)
    raise RuntimeError("Errore creazione utente")


async def delete_user(username: str) -> bool:
    normalized = _normalize_username(username)
    if not is_db_available():
        with _LOCK:
            payload = _read_data()
            before = len(payload.get("users", []))
            payload["users"] = [
                user for user in payload.get("users", [])
                if _normalize_username(user.get("username")) != normalized
            ]
            changed = len(payload["users"]) != before
            if changed:
                _write_data(payload)
            return changed

    async with AsyncSessionLocal() as session:
        result = await session.execute(delete(DBUser).where(DBUser.username == normalized))
        await session.commit()
        await _sync_db_users_backup(session)
        return result.rowcount > 0
    return False


async def reset_password(username: str, password: str) -> dict:
    normalized = _normalize_username(username)
    if len(password or "") < 6:
        raise ValueError("Password troppo corta: minimo 6 caratteri")

    if not is_db_available():
        with _LOCK:
            payload = _read_data()
            user = _find_user(payload, normalized)
            if not user:
                raise ValueError("Utente non trovato")
            pwd_rec = _build_password_record(password)
            user["password"] = pwd_rec
            user["updated_at"] = _utc_now()
            _write_data(payload)
            return {
                "username": user.get("username"),
                "status": _normalize_status(user.get("status")),
                "updated_at": user.get("updated_at"),
            }

    pwd_rec = _build_password_record(password)

    async with AsyncSessionLocal() as session:
        user = await session.get(DBUser, normalized)
        if not user:
            raise ValueError("Utente non trovato")
        user.password_hash = pwd_rec["hash"]
        user.password_salt = pwd_rec["salt"]
        user.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await _sync_db_users_backup(session)
        await session.refresh(user)
        return {"username": user.username, "status": user.status, "updated_at": user.updated_at.isoformat()}
    raise RuntimeError("Errore reset password")


async def update_user(
    username: str,
    *,
    status: Optional[str] = None,
    plan: Optional[str] = None,
    expires_at: Optional[str] = None,
    notes: Optional[str] = None,
    ai_provider: Optional[str] = None,
    claude_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    google_api_key: Optional[str] = None,
) -> dict:
    normalized = _normalize_username(username)
    if not is_db_available():
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
            if ai_provider is not None:
                user["ai_provider"] = _normalize_ai_provider(ai_provider)
            if claude_api_key is not None:
                user["claude_api_key"] = str(claude_api_key).strip()
            if openai_api_key is not None:
                user["openai_api_key"] = str(openai_api_key).strip()
            if google_api_key is not None:
                user["google_api_key"] = str(google_api_key).strip()
            if _is_expired(user.get("expires_at")):
                user["status"] = "expired"

            user["updated_at"] = _utc_now()
            _write_data(payload)
            return _legacy_user_to_public_dict(user)

    async with AsyncSessionLocal() as session:
        user = await session.get(DBUser, normalized)
        if not user:
            raise ValueError("Utente non trovato")
        
        if status is not None:
            user.status = _normalize_status(status)
        if plan is not None:
            user.plan = _normalize_plan(plan)
        if expires_at is not None:
            user.expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00")) if expires_at else None
        if notes is not None:
            user.notes = str(notes).strip()
        if ai_provider is not None:
            user.ai_provider = str(ai_provider).strip()
        if claude_api_key is not None:
            user.claude_api_key = str(claude_api_key).strip()
        if openai_api_key is not None:
            user.openai_api_key = str(openai_api_key).strip()
        if google_api_key is not None:
            user.google_api_key = str(google_api_key).strip()
        
        # Check expiry
        if user.expires_at and user.expires_at <= datetime.now(timezone.utc):
            user.status = "expired"
            
        user.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await _sync_db_users_backup(session)
        await session.refresh(user)
        return _user_to_dict(user)


async def verify_user(username: str, password: str) -> Optional[dict]:
    normalized = _normalize_username(username)
    if not is_db_available():
        with _LOCK:
            payload = _read_data()
            user = _find_user(payload, normalized)
            if not user:
                return None
            if _is_expired(user.get("expires_at")):
                user["status"] = "expired"
                user["updated_at"] = _utc_now()
                _write_data(payload)
                return None
            if _normalize_status(user.get("status")) != "active":
                return None
            if not _legacy_verify_password(user, password):
                return None
            user["last_login_at"] = _utc_now()
            user["updated_at"] = _utc_now()
            _write_data(payload)
            return _legacy_user_to_public_dict(user)

    async with AsyncSessionLocal() as session:
        user = await session.get(DBUser, normalized)
        if not user:
            return None
        
        # Check status and expiry
        if user.expires_at and user.expires_at <= datetime.now(timezone.utc):
            user.status = "expired"
            await session.commit()
            return None
            
        if user.status != "active":
            return None
        
        candidate_hash = _hash_password(password, user.password_salt)
        if not secrets.compare_digest(candidate_hash, user.password_hash):
            return None
        
        user.last_login_at = datetime.now(timezone.utc)
        await session.commit()
        await _sync_db_users_backup(session)
        await session.refresh(user)
        return _user_to_dict(user)
    return None


async def get_user_count() -> int:
    if not is_db_available():
        with _LOCK:
            return len(_read_data().get("users", []))
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(func.count(DBUser.username)))
        return result.scalar() or 0
    return 0


async def get_user_profile(username: str) -> Optional[dict]:
    normalized = _normalize_username(username)
    if not is_db_available():
        with _LOCK:
            payload = _read_data()
            user = _find_user(payload, normalized)
            return _legacy_user_to_public_dict(user) if user else None
    async with AsyncSessionLocal() as session:
        user = await session.get(DBUser, normalized)
        return _user_to_dict(user) if user else None
    return None


async def get_user_ai_credentials(username: str) -> dict:
    normalized = _normalize_username(username)
    if not is_db_available():
        with _LOCK:
            payload = _read_data()
            user = _find_user(payload, normalized)
            if not user:
                return {"provider": "anthropic", "api_key": ""}
            provider = _normalize_ai_provider(user.get("ai_provider"))
            key = ""
            if provider == "openai":
                key = str(user.get("openai_api_key") or "").strip()
            elif provider == "google":
                key = str(user.get("google_api_key") or "").strip()
            else:
                key = str(user.get("claude_api_key") or "").strip()
            if not key:
                if str(user.get("google_api_key") or "").strip():
                    provider = "google"
                    key = str(user.get("google_api_key") or "").strip()
                elif str(user.get("openai_api_key") or "").strip():
                    provider = "openai"
                    key = str(user.get("openai_api_key") or "").strip()
                elif str(user.get("claude_api_key") or "").strip():
                    provider = "anthropic"
                    key = str(user.get("claude_api_key") or "").strip()
            return {"provider": provider, "api_key": key}
        
    async with AsyncSessionLocal() as session:
        user = await session.get(DBUser, normalized)
        if not user:
            return {"provider": "anthropic", "api_key": ""}
        
        provider = (user.ai_provider or "anthropic").strip().lower()
        key = ""
        if provider == "openai":
            key = (user.openai_api_key or "").strip()
        elif provider == "google":
            key = (user.google_api_key or "").strip()
        else:
            key = (user.claude_api_key or "").strip()

        # Fallback to any available key
        if not key:
            if (user.google_api_key or "").strip():
                provider = "google"
                key = user.google_api_key.strip()
            elif (user.openai_api_key or "").strip():
                provider = "openai"
                key = user.openai_api_key.strip()
            elif (user.claude_api_key or "").strip():
                provider = "anthropic"
                key = user.claude_api_key.strip()

        return {"provider": provider, "api_key": key}
    return {"provider": "anthropic", "api_key": ""}


async def get_user_claude_api_key(username: str) -> str:
    normalized = _normalize_username(username)
    if not is_db_available():
        with _LOCK:
            payload = _read_data()
            user = _find_user(payload, normalized)
            return str((user or {}).get("claude_api_key") or "").strip()
    async with AsyncSessionLocal() as session:
        user = await session.get(DBUser, normalized)
        return user.claude_api_key or "" if user else ""
    return ""


# ─── Billing / Referral ─────────────────────────────────────────────────────

_BILLING_FIELDS = {
    "email",
    "stripe_customer_id",
    "stripe_subscription_id",
    "subscription_status",
    "referral_code",
    "referred_by",
    "free_months_credit",
    "referral_count",
    "status",
    "plan",
}


def _generate_referral_code(username: str) -> str:
    """Codice referral leggibile: prefisso username + token random."""
    prefix = "".join(c for c in _normalize_username(username) if c.isalnum())[:6].upper()
    if len(prefix) < 3:
        prefix = "VTR"
    return f"{prefix}-{secrets.token_hex(3).upper()}"


async def _apply_billing_updates(username: str, updates: dict) -> Optional[dict]:
    """Applica un set di aggiornamenti billing/referral (DB + legacy)."""
    normalized = _normalize_username(username)
    safe = {k: v for k, v in updates.items() if k in _BILLING_FIELDS}
    if not safe:
        return await get_user_profile(normalized)

    if not is_db_available():
        with _LOCK:
            payload = _read_data()
            user = _find_user(payload, normalized)
            if not user:
                return None
            user.update(safe)
            user["updated_at"] = _utc_now()
            _write_data(payload)
            return _legacy_user_to_public_dict(user)

    async with AsyncSessionLocal() as session:
        user = await session.get(DBUser, normalized)
        if not user:
            return None
        for key, value in safe.items():
            setattr(user, key, value)
        user.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await _sync_db_users_backup(session)
        await session.refresh(user)
        return _user_to_dict(user)
    return None


async def ensure_referral_code(username: str) -> str:
    """Restituisce il codice referral dell'utente, creandolo se assente."""
    normalized = _normalize_username(username)
    profile = await get_user_profile(normalized)
    if not profile:
        raise ValueError("Utente non trovato")
    existing = profile.get("referral_code")
    if existing:
        return existing
    # Genera un codice unico (riprova in caso di collisione)
    for _ in range(8):
        code = _generate_referral_code(normalized)
        if not await get_user_by_referral_code(code):
            await _apply_billing_updates(normalized, {"referral_code": code})
            return code
    raise RuntimeError("Impossibile generare un codice referral unico")


async def get_user_by_referral_code(code: str) -> Optional[dict]:
    target = str(code or "").strip().upper()
    if not target:
        return None
    if not is_db_available():
        with _LOCK:
            payload = _read_data()
            for user in payload.get("users", []):
                if str(user.get("referral_code") or "").strip().upper() == target:
                    return _legacy_user_to_public_dict(user)
            return None
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DBUser).where(func.upper(DBUser.referral_code) == target)
        )
        user = result.scalars().first()
        return _user_to_dict(user) if user else None
    return None


async def get_user_by_stripe_customer(customer_id: str) -> Optional[dict]:
    target = str(customer_id or "").strip()
    if not target:
        return None
    if not is_db_available():
        with _LOCK:
            payload = _read_data()
            for user in payload.get("users", []):
                if str(user.get("stripe_customer_id") or "").strip() == target:
                    return _legacy_user_to_public_dict(user)
            return None
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DBUser).where(DBUser.stripe_customer_id == target)
        )
        user = result.scalars().first()
        return _user_to_dict(user) if user else None
    return None


async def create_pending_user(
    username: str,
    password: str,
    *,
    email: Optional[str] = None,
    referred_by: Optional[str] = None,
) -> dict:
    """
    Crea un utente in stato 'pending' (non può accedere finché il pagamento
    non è confermato dal webhook Stripe). Genera subito il suo codice referral.
    """
    normalized = _normalize_username(username)
    if len(normalized) < 3:
        raise ValueError("Username/email troppo corto")
    if len(password or "") < 6:
        raise ValueError("Password troppo corta: minimo 6 caratteri")

    referral_code = _generate_referral_code(normalized)
    referred_clean = str(referred_by or "").strip().upper() or None

    if not is_db_available():
        with _LOCK:
            payload = _read_data()
            if _find_user(payload, normalized):
                raise ValueError("Account già esistente con questa email")
            record = {
                "username": normalized,
                "email": email or normalized,
                "password": _build_password_record(password),
                "status": "pending",
                "plan": "standard",
                "expires_at": None,
                "notes": "",
                "ai_provider": "anthropic",
                "claude_api_key": "",
                "openai_api_key": "",
                "google_api_key": "",
                "stripe_customer_id": None,
                "stripe_subscription_id": None,
                "subscription_status": "none",
                "referral_code": referral_code,
                "referred_by": referred_clean,
                "free_months_credit": 0,
                "referral_count": 0,
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
                "last_login_at": None,
            }
            payload.setdefault("users", []).append(record)
            payload["users"].sort(key=lambda i: str(i.get("username") or ""))
            _write_data(payload)
            return _legacy_user_to_public_dict(record)

    pwd_rec = _build_password_record(password)
    async with AsyncSessionLocal() as session:
        if await session.get(DBUser, normalized):
            raise ValueError("Account già esistente con questa email")
        user = DBUser(
            username=normalized,
            email=email or normalized,
            password_hash=pwd_rec["hash"],
            password_salt=pwd_rec["salt"],
            status="pending",
            plan="standard",
            ai_provider="anthropic",
            subscription_status="none",
            referral_code=referral_code,
            referred_by=referred_clean,
            free_months_credit=0,
            referral_count=0,
        )
        session.add(user)
        await session.commit()
        await _sync_db_users_backup(session)
        await session.refresh(user)
        return _user_to_dict(user)
    raise RuntimeError("Errore creazione account")


async def set_subscription(
    username: str,
    *,
    stripe_customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    subscription_status: Optional[str] = None,
    activate: bool = False,
    deactivate: bool = False,
) -> Optional[dict]:
    """Aggiorna lo stato abbonamento di un utente dopo eventi Stripe."""
    updates: dict = {}
    if stripe_customer_id is not None:
        updates["stripe_customer_id"] = stripe_customer_id
    if stripe_subscription_id is not None:
        updates["stripe_subscription_id"] = stripe_subscription_id
    if subscription_status is not None:
        updates["subscription_status"] = subscription_status
    if activate:
        updates["status"] = "active"
    if deactivate:
        updates["status"] = "suspended"
    return await _apply_billing_updates(username, updates)


async def credit_referrer(referral_code: str) -> Optional[dict]:
    """
    Accredita +1 mese gratis e +1 al conteggio referral al proprietario del codice.
    Chiamato quando un amico invitato completa il primo pagamento.
    """
    referrer = await get_user_by_referral_code(referral_code)
    if not referrer:
        return None
    new_credit = int(referrer.get("free_months_credit") or 0) + 1
    new_count = int(referrer.get("referral_count") or 0) + 1
    return await _apply_billing_updates(
        referrer["username"],
        {"free_months_credit": new_credit, "referral_count": new_count},
    )


async def consume_free_month(username: str) -> Optional[dict]:
    """Decrementa di 1 il credito mesi gratis (dopo averlo applicato su Stripe)."""
    profile = await get_user_profile(username)
    if not profile:
        return None
    current = int(profile.get("free_months_credit") or 0)
    if current <= 0:
        return profile
    return await _apply_billing_updates(username, {"free_months_credit": current - 1})


async def get_billing_record(username: str) -> Optional[dict]:
    """Record interno con gli ID Stripe (NON esporre in API pubbliche)."""
    normalized = _normalize_username(username)
    if not is_db_available():
        with _LOCK:
            payload = _read_data()
            user = _find_user(payload, normalized)
            if not user:
                return None
            return {
                "username": user.get("username"),
                "email": user.get("email"),
                "stripe_customer_id": user.get("stripe_customer_id"),
                "stripe_subscription_id": user.get("stripe_subscription_id"),
                "subscription_status": user.get("subscription_status") or "none",
                "referred_by": user.get("referred_by"),
                "free_months_credit": int(user.get("free_months_credit") or 0),
            }
    async with AsyncSessionLocal() as session:
        user = await session.get(DBUser, normalized)
        if not user:
            return None
        return {
            "username": user.username,
            "email": getattr(user, "email", None),
            "stripe_customer_id": getattr(user, "stripe_customer_id", None),
            "stripe_subscription_id": getattr(user, "stripe_subscription_id", None),
            "subscription_status": getattr(user, "subscription_status", None) or "none",
            "referred_by": getattr(user, "referred_by", None),
            "free_months_credit": int(getattr(user, "free_months_credit", 0) or 0),
        }
    return None
