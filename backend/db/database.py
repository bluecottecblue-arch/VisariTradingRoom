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

# Converti URL PostgreSQL standard al dialetto psycopg3 (libpq SSL nativo).
# psycopg3 capisce ?sslmode=require nativamente — nessun workaround SSL necessario.
if DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

_is_postgres = "postgresql+psycopg://" in DATABASE_URL
_engine_kwargs: dict = {}


# Importa SQLAlchemy solo se disponibile
try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker, DeclarativeBase
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        poolclass=NullPool if _is_postgres else None,
        pool_pre_ping=not _is_postgres,
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


# Colonne aggiunte dopo il primo deploy: vanno create a mano perché
# Base.metadata.create_all NON aggiunge colonne a tabelle già esistenti.
# Ogni ALTER è eseguito in autocommit isolato così un fallimento non blocca gli altri.
_COLUMN_MIGRATIONS: list[tuple[str, str, str]] = [
    ("users", "email", "VARCHAR"),
    ("users", "stripe_customer_id", "VARCHAR"),
    ("users", "stripe_subscription_id", "VARCHAR"),
    ("users", "subscription_status", "VARCHAR DEFAULT 'none'"),
    ("users", "referral_code", "VARCHAR"),
    ("users", "referred_by", "VARCHAR"),
    ("users", "free_months_credit", "INTEGER DEFAULT 0"),
    ("users", "referral_count", "INTEGER DEFAULT 0"),
]


async def _run_lightweight_migrations(conn) -> None:
    """Aggiunge colonne mancanti in modo idempotente (Postgres + SQLite)."""
    from sqlalchemy import text

    for table, column, coltype in _COLUMN_MIGRATIONS:
        if _is_postgres:
            stmt = f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {coltype}'
            try:
                await conn.execute(text(stmt))
            except Exception as exc:  # pragma: no cover
                print(f"⚠️  Migrazione colonna {table}.{column} saltata: {exc}")
        else:
            # SQLite non supporta IF NOT EXISTS su ADD COLUMN: controlla prima
            try:
                res = await conn.execute(text(f"PRAGMA table_info({table})"))
                existing = {row[1] for row in res.fetchall()}
                if column not in existing:
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"))
            except Exception as exc:  # pragma: no cover
                print(f"⚠️  Migrazione colonna {table}.{column} saltata: {exc}")


async def init_db():
    """Inizializza il DB se disponibile, altrimenti usa modalità stateless."""
    global _db_connected, _db_last_error

    if not _sqlalchemy_available:
        print("⚠️  SQLAlchemy non installato — modalità stateless (in-memory). "
              "Installa le dipendenze per persistenza completa.")
        return

    try:
        import db.models  # noqa: F401 - registra i modelli su Base.metadata
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _run_lightweight_migrations(conn)
        _db_connected = True
        _db_last_error = ""
        # Local import to avoid circular dependency
        from modules.auth.user_store import migrate_legacy_users
        await migrate_legacy_users()
        storage_root = resolve_storage_root()
        db_mode = "Postgres" if _is_postgres else "SQLite"
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
        _db_last_error = f"{type(e).__name__}: {e}"
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
