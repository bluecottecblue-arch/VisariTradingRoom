"""
Database — Connessione PostgreSQL opzionale + InMemorySessionStore per sviluppo locale

In sviluppo locale (senza PostgreSQL):
  - init_db() stampa un avviso ma non crasha
  - Tutta la persistenza usa InMemorySessionStore (resettato al riavvio)

In produzione:
  - Imposta DATABASE_URL in .env con la stringa PostgreSQL
  - init_db() crea le tabelle automaticamente
"""
import os
from pathlib import Path


def _backend_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_storage_root() -> Path:
    """
    Determina uno storage root coerente e, quando possibile, durevole.

    Priorità:
    1. PERSISTENT_STORAGE_PATH esplicito
    2. STORAGE_PATH esplicito diverso dal fallback demo ./storage
    3. RENDER_DISK_ROOT se presente
    4. /var/data/strategyforge se disponibile
    5. backend/./storage come fallback locale
    """
    explicit_persistent = (os.environ.get("PERSISTENT_STORAGE_PATH") or "").strip()
    explicit_storage = (os.environ.get("STORAGE_PATH") or "").strip()
    render_disk_root = (os.environ.get("RENDER_DISK_ROOT") or "").strip()

    if explicit_persistent:
        root = Path(explicit_persistent)
    elif explicit_storage and explicit_storage not in {"./storage", "storage"}:
        root = Path(explicit_storage)
    elif render_disk_root:
        root = Path(render_disk_root) / "strategyforge"
    else:
        render_data_root = Path("/var/data")
        if render_data_root.exists() and os.access(render_data_root, os.W_OK):
            root = render_data_root / "strategyforge"
        elif explicit_storage:
            root = Path(explicit_storage)
        else:
            root = Path("./storage")

    if not root.is_absolute():
        root = _backend_root() / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_storage_path(*parts: str) -> Path:
    path = resolve_storage_root()
    for part in parts:
        path = path / part
    return path


storage_dir = str(resolve_storage_root())

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{os.path.join(storage_dir, 'strategyforge.db')}"
)

# Handle Render/Heroku style postgres URLs
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# asyncpg non supporta sslmode= (parametro libpq).
# Rimuoviamo il parametro dall'URL e passiamo ssl=True (booleano) a asyncpg.
# Su Render Linux, asyncpg con ssl=True usa OpenSSL con i CA di sistema
# (Let's Encrypt) che coprono *.frankfurt-postgres.render.com.
_engine_kwargs: dict = {}
if "postgresql+asyncpg://" in DATABASE_URL:
    _needs_ssl = False
    for _param in [
        "sslmode=require", "sslmode=verify-ca", "sslmode=verify-full",
        "ssl=require", "ssl=True",
    ]:
        if _param in DATABASE_URL:
            DATABASE_URL = DATABASE_URL.replace(f"?{_param}", "").replace(f"&{_param}", "")
            _needs_ssl = True
    if _needs_ssl:
        _engine_kwargs["connect_args"] = {"ssl": True}


# Importa SQLAlchemy solo se disponibile
try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker, DeclarativeBase
    from sqlalchemy.pool import NullPool

    _is_postgres = "postgresql+asyncpg://" in DATABASE_URL
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        # NullPool evita connessioni stantie in ambienti cold-start/serverless
        poolclass=NullPool if _is_postgres else None,
        pool_pre_ping=not _is_postgres,  # solo per sqlite
        **_engine_kwargs,
    )
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    class Base(DeclarativeBase):
        pass

    _sqlalchemy_available = True

except ImportError:
    _sqlalchemy_available = False
    engine = None
    AsyncSessionLocal = None

    class Base:  # type: ignore
        metadata = type("M", (), {"create_all": lambda self, bind: None})()


# Runtime connectivity flag – stays False until init_db() confirms the DB connects.
_db_connected: bool = False
_db_last_error: str = ""


def is_db_available() -> bool:
    """Return True only when SQLAlchemy is installed AND a live DB connection was established."""
    return _db_connected


def get_db_last_error() -> str:
    return _db_last_error


def is_sqlalchemy_available() -> bool:
    return _sqlalchemy_available


async def init_db():
    """Inizializza il DB se disponibile, altrimenti usa modalità stateless."""
    import traceback
    global _db_connected, _db_last_error

    if not _sqlalchemy_available:
        print("⚠️  SQLAlchemy non installato — modalità stateless (in-memory). "
              "Installa le dipendenze per persistenza completa.")
        return

    # -- Diagnostica connessione (TCP + asyncpg) --------------------------
    if "postgresql+asyncpg://" in DATABASE_URL:
        from urllib.parse import urlparse
        _raw_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        _parsed = urlparse(_raw_url)
        _pg_host = _parsed.hostname or ""
        _pg_port = _parsed.port or 5432

        # 1) TCP reachability
        import socket as _socket
        try:
            _sock = _socket.create_connection((_pg_host, _pg_port), timeout=10)
            _sock.close()
            print(f"✅ TCP {_pg_host}:{_pg_port} raggiungibile")
        except Exception as _tcp_err:
            _db_last_error = f"TCP_FAIL: {type(_tcp_err).__name__}: {_tcp_err}"
            print(f"❌ TCP {_pg_host}:{_pg_port} NON raggiungibile: {_tcp_err}")
            return

        # 2) asyncpg direct — try ssl=True then ssl=False
        import asyncpg
        _asyncpg_ok = False
        _asyncpg_url = _raw_url
        _all_errors: dict = {}
        for _ssl_val in (True, False):
            try:
                _test_conn = await asyncpg.connect(_asyncpg_url, ssl=_ssl_val, timeout=20)
                await _test_conn.execute("SELECT 1")
                await _test_conn.close()
                print(f"✅ asyncpg direct OK (ssl={_ssl_val!r})")
                _asyncpg_ok = True
                break
            except Exception as _direct_err:
                _tb = traceback.format_exc()
                _emsg = f"{type(_direct_err).__name__}: {_direct_err}"
                _all_errors[f"ssl_{_ssl_val}"] = _emsg + " | " + _tb[-300:]
                print(f"❌ asyncpg ssl={_ssl_val!r}: {_emsg}")
        if not _asyncpg_ok:
            _db_last_error = " ||| ".join(f"{k}: {v[:200]}" for k, v in _all_errors.items())
            print(f"❌ All asyncpg attempts failed: {_db_last_error[:500]}")
            return
    # ---------------------------------------------------------------------

    try:
        import db.models  # noqa: F401 - registra i modelli su Base.metadata
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _db_connected = True
        # Local import to avoid circular dependency
        from modules.auth.user_store import migrate_legacy_users
        await migrate_legacy_users()
        storage_root = resolve_storage_root()
        db_mode = "Postgres" if "postgresql+asyncpg://" in DATABASE_URL else "SQLite"
        print(f"✅ Database connesso e migrazione completata ({db_mode})")
        print(f"📁 Storage root attiva: {storage_root}")
        if (
            db_mode == "SQLite"
            and "/var/data/" not in str(storage_root)
            and "PERSISTENT_STORAGE_PATH" not in os.environ
            and "RENDER_DISK_ROOT" not in os.environ
        ):
            print(
                "⚠️  SQLite sta usando uno storage locale non esplicitamente persistente. "
                "In cloud i dati possono sparire dopo restart o redeploy."
            )
    except Exception as e:
        _db_connected = False
        _db_last_error = f"{type(e).__name__}: {e} | TB: {traceback.format_exc()[:400]}"
        print(f"⚠️  Database non disponibile: {_db_last_error}. Funziona in modalità stateless.")


async def get_db():
    if not is_db_available() or AsyncSessionLocal is None:
        yield None
        return
    async with AsyncSessionLocal() as session:
        yield session



class InMemorySessionStore:
    """
    Store in-memory per sviluppo locale senza PostgreSQL.
    I dati vengono persi al riavvio del backend.
    In produzione: sostituire con query al DB tramite get_db().
    """
    _store: dict = {}

    @classmethod
    def save(cls, session_id: str, key: str, value) -> None:
        if session_id not in cls._store:
            cls._store[session_id] = {}
        cls._store[session_id][key] = value

    @classmethod
    def get(cls, session_id: str, key: str = None):
        if key:
            return cls._store.get(session_id, {}).get(key)
        return cls._store.get(session_id, {})

    @classmethod
    def list_sessions(cls) -> list:
        return list(cls._store.keys())

    @classmethod
    def delete(cls, session_id: str) -> None:
        cls._store.pop(session_id, None)
