"""
SQLite persistence layer for Vidalyze analysis history.

Stores a lightweight summary of each completed analysis (no full comment list).
The database file is created automatically on first use.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "vidalyze.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS analyses (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id         TEXT NOT NULL,
    video_title      TEXT NOT NULL DEFAULT '',
    youtube_url      TEXT NOT NULL DEFAULT '',
    analysis_method  TEXT NOT NULL DEFAULT '',
    total_comments   INTEGER NOT NULL DEFAULT 0,
    overall_sentiment TEXT NOT NULL DEFAULT '{}',   -- JSON {sentiment: pct}
    comment_categories TEXT NOT NULL DEFAULT '{}',  -- JSON {category: count}
    overall_insights TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL
)
"""
_CREATE_INDEX = "CREATE INDEX IF NOT EXISTS idx_video_id ON analyses (video_id)"


def init_db() -> None:
    """Create the database and tables if they don't already exist."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(_CREATE_TABLE)
            conn.execute(_CREATE_INDEX)
            conn.commit()
        logger.info("Database initialised at %s", DB_PATH)
    except Exception:
        logger.exception("Failed to initialise SQLite database")


def save_analysis(video_id: str, data: dict) -> None:
    """
    Persist a summary of a completed analysis to SQLite.

    Only summary fields are stored — the full comments_data list is
    intentionally excluded to keep the database small.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO analyses
                    (video_id, video_title, youtube_url, analysis_method,
                     total_comments, overall_sentiment, comment_categories,
                     overall_insights, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    datetime.now(tz=timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        logger.info("Saved analysis for video %s to database.", video_id)
    except Exception:
        logger.exception("Failed to save analysis for video %s", video_id)


def get_history(limit: int = 20) -> list[dict]:
    """
    Return the most recent analyses, newest first.
    overall_sentiment and comment_categories are decoded from JSON.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
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
