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

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://sf_user:sf_pass@localhost:5432/strategyforge"
)

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


# Importa SQLAlchemy solo se disponibile
try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker, DeclarativeBase

    engine = create_async_engine(DATABASE_URL, echo=False)
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


async def init_db():
    """Inizializza il DB se disponibile, altrimenti usa modalità stateless."""
    if not _sqlalchemy_available:
        print("⚠️  SQLAlchemy non installato — modalità stateless (in-memory). "
              "Installa le dipendenze per persistenza completa.")
        return

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database connesso")
    except Exception as e:
        print(f"⚠️  Database non disponibile: {e}. Funziona in modalità stateless.")


async def get_db():
    if not _sqlalchemy_available or AsyncSessionLocal is None:
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
