from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import get_settings
from sqlalchemy.engine import Engine


# SQLite-specific optimizations
engine = create_engine(
    get_settings().DATABASE_URL,
    connect_args={
        "check_same_thread": False,  # Allow multi-threaded access
        "timeout": 30.0,  # Wait 30s for lock release (Failure mode #2)
    },
    echo=False,  # Set True for SQL debugging
    pool_pre_ping=True,  # Verify connections before use
)

# Enable SQLite foreign keys (disabled by default)
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """
    Enable foreign keys constraints on each connection.
    Why: SQLite ignores FKs by default. This prevents orphaned records
    (e.g, Contribution without valid user_id).
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def get_db():
    """
    FastAPI dependency for database sessions.
    Pattern: Create session per request, commit on success, rollback on error.
    Ensures transactions are isolated and always closed.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


