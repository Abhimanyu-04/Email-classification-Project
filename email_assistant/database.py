import logging
import os
import sqlite3
from config import get_settings

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """Ensures the database folder exists and returns an open sqlite3.Connection with Row factory."""
    settings = get_settings()
    db_dir = os.path.dirname(settings.db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Creates the unified emails table if it does not exist and logs an INFO message."""
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS emails (
                message_id TEXT PRIMARY KEY,
                mailpit_id TEXT,
                sender TEXT,
                recipients TEXT,
                subject TEXT,
                body TEXT,
                received_at TEXT,
                fetched_at TEXT,
                analysis_status TEXT NOT NULL DEFAULT 'pending',
                analysis_attempts INTEGER NOT NULL DEFAULT 0,
                analysis_error TEXT,
                analyzed_at TEXT,
                model_name TEXT,
                category TEXT,
                work_type TEXT,
                priority TEXT,
                summary TEXT,
                proposed_actions TEXT,
                due_date TEXT,
                due_time TEXT,
                event_title TEXT,
                event_date TEXT,
                event_time TEXT,
                event_location TEXT,
                todo_items TEXT,
                date_phrase TEXT,
                confidence REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'proposed',
                result TEXT,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(message_id, action_type)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("Database is ready.")
