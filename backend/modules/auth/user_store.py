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
        user.setdefault("ai_provider", "anthropic")
        user.setdefault("claude_api_key", "")
        user.setdefault("openai_api_key", "")
        user.setdefault("google_api_key", "")
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


from sqlalchemy import select, update, delete, func
from db.database import is_db_available, AsyncSessionLocal
from db.models import User as DBUser


def _user_to_dict(user: DBUser) -> dict:
    return {
        "username": user.username,
        "status": user.status,
        "plan": user.plan,
        "expires_at": user.expires_at.isoformat() if user.expires_at else None,
        "notes": user.notes or "",
        "ai_provider": user.ai_provider,
        "claude_key_configured": bool(user.claude_api_key),
        "openai_key_configured": bool(user.openai_api_key),
        "google_key_configured": bool(user.google_api_key),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


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
        return []

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
        raise RuntimeError("Database non disponibile — registrazione disabilitata")

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
        await session.refresh(user)
        return _user_to_dict(user)
    raise RuntimeError("Errore creazione utente")


async def delete_user(username: str) -> bool:
    normalized = _normalize_username(username)
    if not is_db_available():
        return False

    async with AsyncSessionLocal() as session:
        result = await session.execute(delete(DBUser).where(DBUser.username == normalized))
        await session.commit()
        return result.rowcount > 0
    return False


async def reset_password(username: str, password: str) -> dict:
    normalized = _normalize_username(username)
    if len(password or "") < 6:
        raise ValueError("Password troppo corta: minimo 6 caratteri")

    if not is_db_available():
        raise RuntimeError("Database non disponibile")

    pwd_rec = _build_password_record(password)

    async with AsyncSessionLocal() as session:
        user = await session.get(DBUser, normalized)
        if not user:
            raise ValueError("Utente non trovato")
        user.password_hash = pwd_rec["hash"]
        user.password_salt = pwd_rec["salt"]
        user.updated_at = datetime.now(timezone.utc)
        await session.commit()
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
        raise RuntimeError("Database non disponibile")

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
        await session.refresh(user)
        return _user_to_dict(user)


async def verify_user(username: str, password: str) -> Optional[dict]:
    normalized = _normalize_username(username)
    if not is_db_available():
        return None

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
        return _user_to_dict(user)
    return None


async def get_user_count() -> int:
    if not is_db_available():
        return 0
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(func.count(DBUser.username)))
        return result.scalar() or 0
    return 0


async def get_user_profile(username: str) -> Optional[dict]:
    normalized = _normalize_username(username)
    if not is_db_available():
        return None
    async with AsyncSessionLocal() as session:
        user = await session.get(DBUser, normalized)
        return _user_to_dict(user) if user else None
    return None


async def get_user_ai_credentials(username: str) -> dict:
    normalized = _normalize_username(username)
    if not is_db_available():
        return {"provider": "anthropic", "api_key": ""}
        
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
        return ""
    async with AsyncSessionLocal() as session:
        user = await session.get(DBUser, normalized)
        return user.claude_api_key or "" if user else ""
    return ""
