# Transaction Model:
# - One DB transaction per HTTP request
# - Commit happens automatically if request succeeds
# - Any exception triggers rollback
# - Routes MUST NOT call db.commit() directly
"""
Database configuration and session management.

HARDENING UPDATES:
- Explicit commit/rollback in get_db
- Error logging for debugging
- Foreign key enforcement
"""

from sqlalchemy.exc import SQLAlchemyError
import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import get_settings
from sqlalchemy.engine import Engine


logger = logging.getLogger(__name__)
settings = get_settings()


# SQLite-specific optimizations
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={
        "check_same_thread": False,  # Allow multi-threaded access
        "timeout": 30.0,  # Wait 30s for lock release (Failure mode #2)
    },
    echo=False,  # Set True for SQL debugging
    pool_pre_ping=True,  # Verify connections before use
)

# Enable SQLite foreign keys (disabled by default)
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    Enable foreign keys constraints on each connection.
    Why: SQLite ignores FKs by default. This prevents orphaned records
    (e.g, Contribution without valid user_id).
    """
    cursor = dbapi_connection.cursor()
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
    Hardening additions:
    - Explicit exception logging
    - Connection validation (pool_pre_ping already enabled)
    - Error context for debugging

    Lifecycle:
    1. Create session
    2. Yield to endpoint
    3. Commit on success
    4. Rollback on exception
    5. Always close session
    """
    db = SessionLocal()
    try:
        yield db
        # Explicit commit (FastAPI doesn't auto-commit)
        # Only if no exception raised
        db.commit()
    except SQLAlchemyError as e:
        # Rollback on database error
        db.rollback()
        logger.error(f"Database error in request: {e}", exc_info=True)
        # Re-raise to trigger FastAPI's 500 handler
        raise
    except Exception as e:
        # Rollback on any error (even non-DB)
        db.rollback()
        logger.error(f"Unexpected error, rolling back DB: {e}", exc_info=True)
        raise
    finally:
        # Always close session
        db.close()


