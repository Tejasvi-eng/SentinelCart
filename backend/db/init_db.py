"""
Database initialization.

Creates tables and audit log triggers.

Run with: python -m backend.db.init_db
"""

import sqlite3

from sqlalchemy import event, text

from backend.db.models import Base
from backend.db.session import DATABASE_URL, engine


def create_tables() -> None:
    """Create all tables defined in models."""
    Base.metadata.create_all(bind=engine)
    print("✓ Tables created")


def enable_foreign_keys() -> None:
    """Enable foreign-key constraint enforcement in SQLite."""
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
    print("✓ Foreign-key enforcement enabled")


def create_audit_log_triggers() -> None:
    """
    Create SQLite triggers to prevent UPDATE and DELETE on audit_log.
    
    This ensures audit_log is append-only.
    """
    db_path = DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Trigger to reject UPDATE
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS audit_log_prevent_update
        BEFORE UPDATE ON audit_log
        BEGIN
            SELECT RAISE(ABORT, 'audit_log table is append-only and cannot be updated');
        END
    """)

    # Trigger to reject DELETE
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS audit_log_prevent_delete
        BEFORE DELETE ON audit_log
        BEGIN
            SELECT RAISE(ABORT, 'audit_log table is append-only and cannot be deleted');
        END
    """)

    conn.commit()
    conn.close()
    print("✓ Audit log append-only triggers created")


def init_db() -> None:
    """Initialize the database: create tables and triggers."""
    print("Initializing SentinelCart database...")
    create_tables()
    enable_foreign_keys()
    create_audit_log_triggers()
    print("✓ Database initialization complete\n")


if __name__ == "__main__":
    init_db()
