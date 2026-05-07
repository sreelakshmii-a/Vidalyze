"""
SQLite persistence layer for Vidalyze analysis history.

Stores a lightweight summary of each completed analysis (no full comment list).
The database file is created automatically on first use.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# DB_DIR can be overridden via environment variable so the production
# container can write to a mounted volume outside the app directory.
_DB_DIR = Path(os.getenv("DB_DIR", str(Path(__file__).parent)))
DB_PATH = _DB_DIR / "vidalyze.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS analyses (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id           TEXT NOT NULL,
    video_title        TEXT NOT NULL DEFAULT '',
    youtube_url        TEXT NOT NULL DEFAULT '',
    analysis_method    TEXT NOT NULL DEFAULT '',
    total_comments     INTEGER NOT NULL DEFAULT 0,
    overall_sentiment  TEXT NOT NULL DEFAULT '{}',   -- JSON {sentiment: pct}
    comment_categories TEXT NOT NULL DEFAULT '{}',  -- JSON {category: count}
    overall_insights   TEXT NOT NULL DEFAULT '',
    session_id         TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL
)
"""
_CREATE_INDEX         = "CREATE INDEX IF NOT EXISTS idx_video_id  ON analyses (video_id)"
_CREATE_SESSION_INDEX = "CREATE INDEX IF NOT EXISTS idx_session_id ON analyses (session_id)"


def _migrate_db(conn: sqlite3.Connection) -> None:
    """Apply any pending schema migrations. Safe to run on every startup."""
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(analyses)")}
    if "session_id" not in existing_cols:
        conn.execute("ALTER TABLE analyses ADD COLUMN session_id TEXT NOT NULL DEFAULT ''")
        conn.execute(_CREATE_SESSION_INDEX)
        logger.info("Migration applied: added session_id column to analyses table")


def init_db() -> None:
    """Create the database and tables if they don't already exist, then migrate."""
    try:
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            # WAL mode allows concurrent reads alongside a single writer.
            # Essential with multiple gunicorn workers sharing one SQLite file.
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(_CREATE_TABLE)
            conn.execute(_CREATE_INDEX)
            _migrate_db(conn)           # adds session_id column to legacy DBs first
            conn.execute(_CREATE_SESSION_INDEX)  # safe now — column always exists
            conn.commit()
        logger.info("Database initialised at %s", DB_PATH)
    except Exception:
        logger.exception("Failed to initialise SQLite database")


def save_analysis(video_id: str, data: dict, session_id: str = "") -> None:
    """
    Persist a summary of a completed analysis to SQLite.

    Only summary fields are stored — the full comments_data list is
    intentionally excluded to keep the database small.
    session_id scopes the record to a specific browser session so that
    /history only returns the requesting user's own analyses.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO analyses
                    (video_id, video_title, youtube_url, analysis_method,
                     total_comments, overall_sentiment, comment_categories,
                     overall_insights, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    data.get("video_title", ""),
                    data.get("youtube_url", ""),
                    data.get("analysis_method", ""),
                    data.get("total_comments", 0),
                    json.dumps(data.get("overall_sentiment", {})),
                    json.dumps(data.get("comment_categories", {})),
                    data.get("overall_insights", ""),
                    session_id,
                    datetime.now(tz=timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        logger.info("Saved analysis for video %s (session %s).", video_id, session_id or "anonymous")
    except Exception:
        logger.exception("Failed to save analysis for video %s", video_id)


def get_history(limit: int = 20, session_id: str = "") -> list[dict]:
    """
    Return the most recent analyses for a given session, newest first.
    When session_id is empty all records are returned (dev/admin fallback).
    overall_sentiment and comment_categories are decoded from JSON.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            if session_id:
                rows = conn.execute(
                    """
                    SELECT id, video_id, video_title, youtube_url, analysis_method,
                           total_comments, overall_sentiment, comment_categories, created_at
                    FROM   analyses
                    WHERE  session_id = ?
                    ORDER  BY created_at DESC
                    LIMIT  ?
                    """,
                    (session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, video_id, video_title, youtube_url, analysis_method,
                           total_comments, overall_sentiment, comment_categories, created_at
                    FROM   analyses
                    ORDER  BY created_at DESC
                    LIMIT  ?
                    """,
                    (limit,),
                ).fetchall()

        records = []
        for row in rows:
            record = dict(row)
            record["overall_sentiment"]   = json.loads(record["overall_sentiment"])
            record["comment_categories"]  = json.loads(record["comment_categories"])
            records.append(record)
        return records

    except Exception:
        logger.exception("Failed to fetch analysis history")
        return []


def get_record_count() -> int:
    """Return the total number of stored analyses (useful for tests)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
    except Exception:
        return 0
