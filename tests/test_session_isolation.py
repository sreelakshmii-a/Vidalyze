"""
Tests for Phase 1 — per-session history isolation.

Covers three layers:
  1. storage.py  — session_id persisted; get_history filters correctly
  2. migration   — existing DB without session_id column is upgraded safely
  3. app.py      — X-Session-Id header validated, threaded through to storage
"""
import os
import sqlite3
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SID_A = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
SID_B = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"

_SAMPLE = {
    "youtube_url":        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "video_title":        "Rick Astley — Never Gonna Give You Up",
    "total_comments":     250,
    "analysis_method":    "Gemini",
    "overall_sentiment":  {"Positive": 70.0, "Neutral": 20.0, "Negative": 10.0},
    "comment_categories": {"Positive": 175, "Neutral": 50, "Help": 25},
    "overall_insights":   "## Summary\n\nVery positive.",
    "highlights":         {"top_insights": [], "top_complaints": [], "feature_requests": []},
    "cached":             False,
}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """Fresh database for each test — never touches vidalyze.db."""
    db_file = tmp_path / "test.db"
    with patch("storage.DB_PATH", db_file):
        import storage
        storage.init_db()
        yield db_file


@pytest.fixture
def legacy_db(tmp_path):
    """
    Database created with the OLD schema (no session_id column).
    Used to verify that the migration path runs correctly.
    """
    db_file = tmp_path / "legacy.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute("""
            CREATE TABLE analyses (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id           TEXT NOT NULL,
                video_title        TEXT NOT NULL DEFAULT '',
                youtube_url        TEXT NOT NULL DEFAULT '',
                analysis_method    TEXT NOT NULL DEFAULT '',
                total_comments     INTEGER NOT NULL DEFAULT 0,
                overall_sentiment  TEXT NOT NULL DEFAULT '{}',
                comment_categories TEXT NOT NULL DEFAULT '{}',
                overall_insights   TEXT NOT NULL DEFAULT '',
                created_at         TEXT NOT NULL
            )
        """)
        conn.commit()
    return db_file


# ═══════════════════════════════════════════════════════════════════════════════
# 1. storage.py — session isolation
# ═══════════════════════════════════════════════════════════════════════════════

class TestSaveAnalysisSessionId:
    def test_session_id_persisted_in_db(self, tmp_db):
        """session_id written to save_analysis must appear verbatim in the row."""
        from storage import save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("vid00000001", _SAMPLE, session_id=SID_A)

        with sqlite3.connect(tmp_db) as conn:
            row = conn.execute("SELECT session_id FROM analyses").fetchone()
        assert row[0] == SID_A

    def test_default_session_id_is_empty_string(self, tmp_db):
        """Calling save_analysis without session_id must store an empty string."""
        from storage import save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("vid00000002", _SAMPLE)

        with sqlite3.connect(tmp_db) as conn:
            row = conn.execute("SELECT session_id FROM analyses").fetchone()
        assert row[0] == ""

    def test_multiple_sessions_stored_independently(self, tmp_db):
        """Records from two different sessions must coexist in the table."""
        from storage import get_record_count, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("vid00000003", _SAMPLE, session_id=SID_A)
            save_analysis("vid00000004", _SAMPLE, session_id=SID_B)
            assert get_record_count() == 2


class TestGetHistorySessionIsolation:
    def test_returns_only_own_session_records(self, tmp_db):
        """User A must not see user B's analyses."""
        from storage import get_history, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("vid00000005", {**_SAMPLE, "video_title": "A Video"}, session_id=SID_A)
            save_analysis("vid00000006", {**_SAMPLE, "video_title": "B Video"}, session_id=SID_B)
            result_a = get_history(session_id=SID_A)
            result_b = get_history(session_id=SID_B)

        assert len(result_a) == 1
        assert result_a[0]["video_title"] == "A Video"
        assert len(result_b) == 1
        assert result_b[0]["video_title"] == "B Video"

    def test_unknown_session_returns_empty(self, tmp_db):
        """A session that has never analyzed anything sees an empty list."""
        from storage import get_history, save_analysis
        unknown_sid = "cccccccc-cccc-4ccc-cccc-cccccccccccc"
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("vid00000007", _SAMPLE, session_id=SID_A)
            result = get_history(session_id=unknown_sid)
        assert result == []

    def test_empty_session_id_returns_all_records(self, tmp_db):
        """Passing session_id='' (admin / no-header fallback) returns everything."""
        from storage import get_history, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("vid00000008", _SAMPLE, session_id=SID_A)
            save_analysis("vid00000009", _SAMPLE, session_id=SID_B)
            result = get_history(session_id="")
        assert len(result) == 2

    def test_user_with_multiple_analyses_sees_all_own(self, tmp_db):
        """A user who analyzed 3 videos must see all 3, not a stranger's."""
        from storage import get_history, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            for i in range(3):
                save_analysis(f"vid{i:011d}", {**_SAMPLE, "video_title": f"My Video {i}"}, session_id=SID_A)
            save_analysis("vid99999999z", {**_SAMPLE, "video_title": "Stranger Video"}, session_id=SID_B)
            result = get_history(session_id=SID_A)

        assert len(result) == 3
        titles = {r["video_title"] for r in result}
        assert "Stranger Video" not in titles

    def test_limit_applies_within_session(self, tmp_db):
        """limit= must be applied after the session filter, not before."""
        from storage import get_history, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            for i in range(5):
                save_analysis(f"vid{i:011d}", _SAMPLE, session_id=SID_A)
            result = get_history(limit=2, session_id=SID_A)
        assert len(result) == 2

    def test_newest_first_within_session(self, tmp_db):
        """Results must still be ordered newest-first within a session."""
        from storage import get_history, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("vid00000010", {**_SAMPLE, "video_title": "Older"}, session_id=SID_A)
            save_analysis("vid00000011", {**_SAMPLE, "video_title": "Newer"}, session_id=SID_A)
            result = get_history(session_id=SID_A)

        assert result[0]["video_title"] == "Newer"
        assert result[1]["video_title"] == "Older"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Migration — existing DB without session_id
# ═══════════════════════════════════════════════════════════════════════════════

class TestMigration:
    def test_adds_session_id_column_to_legacy_db(self, legacy_db):
        """init_db on an old schema must add the session_id column."""
        with patch("storage.DB_PATH", legacy_db):
            from storage import init_db
            init_db()

        with sqlite3.connect(legacy_db) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(analyses)")}
        assert "session_id" in cols

    def test_migration_is_idempotent(self, legacy_db):
        """Running init_db twice on an already-migrated DB must not raise."""
        with patch("storage.DB_PATH", legacy_db):
            from storage import init_db
            init_db()
            init_db()  # second call — no exception

    def test_migration_preserves_existing_rows(self, legacy_db):
        """Pre-migration rows must survive and have session_id = ''."""
        with sqlite3.connect(legacy_db) as conn:
            conn.execute("""
                INSERT INTO analyses
                    (video_id, video_title, youtube_url, analysis_method,
                     total_comments, overall_sentiment, comment_categories,
                     overall_insights, created_at)
                VALUES ('oldvid0001', 'Old Video', 'https://youtube.com', 'TextBlob',
                        10, '{}', '{}', 'insights', '2024-01-01T00:00:00+00:00')
            """)
            conn.commit()

        with patch("storage.DB_PATH", legacy_db):
            from storage import get_record_count, init_db
            init_db()
            count = get_record_count()

        assert count == 1

    def test_migrated_legacy_rows_have_empty_session_id(self, legacy_db):
        """After migration, the pre-existing row must have session_id = ''."""
        with sqlite3.connect(legacy_db) as conn:
            conn.execute("""
                INSERT INTO analyses
                    (video_id, video_title, youtube_url, analysis_method,
                     total_comments, overall_sentiment, comment_categories,
                     overall_insights, created_at)
                VALUES ('oldvid0002', 'Legacy Video', 'https://youtube.com', 'TextBlob',
                        5, '{}', '{}', '', '2024-01-01T00:00:00+00:00')
            """)
            conn.commit()

        with patch("storage.DB_PATH", legacy_db):
            from storage import init_db
            init_db()

        with sqlite3.connect(legacy_db) as conn:
            row = conn.execute("SELECT session_id FROM analyses WHERE video_id='oldvid0002'").fetchone()
        assert row[0] == ""

    def test_legacy_rows_invisible_in_filtered_history(self, legacy_db):
        """Pre-migration rows (session_id='') must NOT appear in a session query."""
        with sqlite3.connect(legacy_db) as conn:
            conn.execute("""
                INSERT INTO analyses
                    (video_id, video_title, youtube_url, analysis_method,
                     total_comments, overall_sentiment, comment_categories,
                     overall_insights, created_at)
                VALUES ('oldvid0003', 'Ghost Video', 'https://youtube.com', 'TextBlob',
                        1, '{}', '{}', '', '2024-01-01T00:00:00+00:00')
            """)
            conn.commit()

        with patch("storage.DB_PATH", legacy_db):
            from storage import get_history, init_db
            init_db()
            result = get_history(session_id=SID_A)

        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# 3. app.py — _get_session_id validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestSessionIdValidation:
    """Test _get_session_id inside a real request context."""

    def test_valid_lowercase_uuid_accepted(self, client):
        """A well-formed lowercase UUID in the header must reach get_history."""
        with patch("app.get_history", return_value=[]) as mock_gh:
            client.get("/history", headers={"X-Session-Id": SID_A})
        mock_gh.assert_called_once_with(limit=20, session_id=SID_A)

    def test_valid_uppercase_uuid_accepted(self, client):
        """UUID matching the pattern case-insensitively must be accepted."""
        upper = SID_A.upper()
        with patch("app.get_history", return_value=[]) as mock_gh:
            client.get("/history", headers={"X-Session-Id": upper})
        _, kwargs = mock_gh.call_args
        assert kwargs["session_id"].lower() == SID_A.lower()

    def test_missing_header_passes_empty_string(self, client):
        """No X-Session-Id header → session_id='' forwarded to storage."""
        with patch("app.get_history", return_value=[]) as mock_gh:
            client.get("/history")
        mock_gh.assert_called_once_with(limit=20, session_id="")

    def test_garbage_string_rejected(self, client):
        """A non-UUID string must be sanitised to '' before reaching storage."""
        with patch("app.get_history", return_value=[]) as mock_gh:
            client.get("/history", headers={"X-Session-Id": "not-a-uuid"})
        mock_gh.assert_called_once_with(limit=20, session_id="")

    def test_sql_injection_rejected(self, client):
        """SQL injection attempt in the header must be sanitised to ''."""
        payload = "' OR '1'='1"
        with patch("app.get_history", return_value=[]) as mock_gh:
            client.get("/history", headers={"X-Session-Id": payload})
        mock_gh.assert_called_once_with(limit=20, session_id="")

    def test_too_short_string_rejected(self, client):
        with patch("app.get_history", return_value=[]) as mock_gh:
            client.get("/history", headers={"X-Session-Id": "1234"})
        mock_gh.assert_called_once_with(limit=20, session_id="")

    def test_uuid_with_extra_chars_rejected(self, client):
        """UUID padded with extra characters must be rejected."""
        with patch("app.get_history", return_value=[]) as mock_gh:
            client.get("/history", headers={"X-Session-Id": SID_A + "EXTRA"})
        mock_gh.assert_called_once_with(limit=20, session_id="")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. app.py — /history route isolation
# ═══════════════════════════════════════════════════════════════════════════════

class TestHistoryRoute:
    def test_returns_200(self, client):
        with patch("app.get_history", return_value=[]):
            resp = client.get("/history", headers={"X-Session-Id": SID_A})
        assert resp.status_code == 200

    def test_returns_json_list(self, client):
        with patch("app.get_history", return_value=[]):
            resp = client.get("/history", headers={"X-Session-Id": SID_A})
        assert isinstance(resp.get_json(), list)

    def test_session_id_forwarded_to_storage(self, client):
        """The exact UUID from the header must be forwarded to get_history."""
        with patch("app.get_history", return_value=[]) as mock_gh:
            client.get("/history", headers={"X-Session-Id": SID_B})
        mock_gh.assert_called_once_with(limit=20, session_id=SID_B)

    def test_two_clients_see_different_histories(self, client):
        """Two separate session IDs must receive their own filtered records."""
        records_a = [{"video_title": "A Video", "video_id": "aaa", "created_at": "2024-01-02"}]
        records_b = [{"video_title": "B Video", "video_id": "bbb", "created_at": "2024-01-01"}]

        def mock_get_history(limit, session_id):
            return records_a if session_id == SID_A else records_b

        with patch("app.get_history", side_effect=mock_get_history):
            resp_a = client.get("/history", headers={"X-Session-Id": SID_A})
            resp_b = client.get("/history", headers={"X-Session-Id": SID_B})

        assert resp_a.get_json()[0]["video_title"] == "A Video"
        assert resp_b.get_json()[0]["video_title"] == "B Video"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. app.py — /analyze saves to correct session
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalyzeSessionId:
    _URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def _analysis_patches(self, sample_comments, sample_categorized):
        return [
            patch("app._get_cached", return_value=None),
            patch("app._set_cached"),
            patch("app.build_youtube_service"),
            patch("app.fetch_video_title", return_value="Test Video"),
            patch("app.fetch_youtube_comments", return_value=(sample_comments, None)),
            patch("app.GEMINI_API_KEY", ""),
            patch("app.analyze_sentiment_fallback", return_value=sample_categorized),
            patch("app.generate_insights_fallback", return_value="Good."),
        ]

    def test_session_id_passed_to_save_analysis(self, client, sample_comments, sample_categorized):
        """save_analysis must receive the exact session_id from the header."""
        p = self._analysis_patches(sample_comments, sample_categorized)
        with p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], \
             patch("app.save_analysis") as mock_save:
            client.post("/analyze",
                        data={"youtube_url": self._URL},
                        headers={"X-Session-Id": SID_A})

        _, _, sid_arg = mock_save.call_args.args
        assert sid_arg == SID_A

    def test_invalid_header_saves_with_empty_session_id(self, client, sample_comments, sample_categorized):
        """An invalid X-Session-Id must be sanitised to '' before save_analysis."""
        p = self._analysis_patches(sample_comments, sample_categorized)
        with p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], \
             patch("app.save_analysis") as mock_save:
            client.post("/analyze",
                        data={"youtube_url": self._URL},
                        headers={"X-Session-Id": "definitely-not-a-uuid"})

        _, _, sid_arg = mock_save.call_args.args
        assert sid_arg == ""

    def test_no_header_saves_with_empty_session_id(self, client, sample_comments, sample_categorized):
        """Missing X-Session-Id header must result in session_id='' in save."""
        p = self._analysis_patches(sample_comments, sample_categorized)
        with p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], \
             patch("app.save_analysis") as mock_save:
            client.post("/analyze", data={"youtube_url": self._URL})

        _, _, sid_arg = mock_save.call_args.args
        assert sid_arg == ""

    def test_cache_hit_still_saves_to_history(self, client):
        """A cache hit must still call save_analysis so history stays current."""
        cached_data = {
            "video_title": "Cached Video", "cached": False,
            "total_comments": 10, "youtube_url": self._URL,
            "overall_sentiment": {"Positive": 100.0},
            "comment_categories": {"Positive": 10},
            "comments_data": [], "overall_insights": "Great.",
            "analysis_method": "Gemini",
        }
        with patch("app._get_cached", return_value=cached_data), \
             patch("app.save_analysis") as mock_save:
            client.post("/analyze",
                        data={"youtube_url": self._URL},
                        headers={"X-Session-Id": SID_B})

        mock_save.assert_called_once()

    def test_cache_hit_saves_with_correct_session_id(self, client):
        """Cache hit save_analysis call must carry the requester's session_id."""
        cached_data = {
            "video_title": "Cached Video", "cached": False,
            "total_comments": 10, "youtube_url": self._URL,
            "overall_sentiment": {"Positive": 100.0},
            "comment_categories": {"Positive": 10},
            "comments_data": [], "overall_insights": "Great.",
            "analysis_method": "Gemini",
        }
        with patch("app._get_cached", return_value=cached_data), \
             patch("app.save_analysis") as mock_save:
            client.post("/analyze",
                        data={"youtube_url": self._URL},
                        headers={"X-Session-Id": SID_B})

        _, _, sid_arg = mock_save.call_args.args
        assert sid_arg == SID_B

    def test_two_sessions_analyzing_same_video_both_saved(self, client, sample_comments, sample_categorized):
        """Two users hitting the same video must each get a save_analysis call."""
        p = self._analysis_patches(sample_comments, sample_categorized)
        saved_sessions = []

        def capture_save(video_id, data, session_id=""):
            saved_sessions.append(session_id)

        with p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], \
             patch("app.save_analysis", side_effect=capture_save):
            client.post("/analyze", data={"youtube_url": self._URL},
                        headers={"X-Session-Id": SID_A})
            client.post("/analyze", data={"youtube_url": self._URL},
                        headers={"X-Session-Id": SID_B})

        assert SID_A in saved_sessions
        assert SID_B in saved_sessions
