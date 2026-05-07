"""
Tests for storage.py — SQLite persistence layer.
Uses a temporary database file so tests never touch vidalyze.db.
"""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    """Redirect DB_PATH to a temporary file for each test."""
    db_file = tmp_path / "test_vidalyze.db"
    with patch("storage.DB_PATH", db_file):
        import storage
        storage.init_db()
        yield db_file


@pytest.fixture
def sample_result():
    return {
        "youtube_url":       "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "video_title":       "Rick Astley — Never Gonna Give You Up",
        "total_comments":    250,
        "analysis_method":   "Gemini",
        "overall_sentiment": {"Positive": 70.0, "Neutral": 20.0, "Negative": 10.0},
        "comment_categories": {"Positive": 175, "Neutral": 50, "Help": 25},
        "overall_insights":  "## Summary\n\nVery positive audience.",
        "highlights":        {"top_insights": [], "top_complaints": [], "feature_requests": []},
        "cached":            False,
    }


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

class TestInitDb:
    def test_creates_db_file(self, tmp_path):
        db_file = tmp_path / "new.db"
        with patch("storage.DB_PATH", db_file):
            from storage import init_db
            init_db()
        assert db_file.exists()

    def test_idempotent(self, tmp_db):
        """Calling init_db twice must not raise."""
        from storage import init_db
        with patch("storage.DB_PATH", tmp_db):
            init_db()
            init_db()  # second call — no exception


# ---------------------------------------------------------------------------
# save_analysis + get_record_count
# ---------------------------------------------------------------------------

class TestSaveAnalysis:
    def test_saves_one_record(self, tmp_db, sample_result):
        from storage import get_record_count, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("dQw4w9WgXcQ", sample_result)
            assert get_record_count() == 1

    def test_saves_multiple_records(self, tmp_db, sample_result):
        from storage import get_record_count, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("aaaaaaaaaaa", sample_result)
            save_analysis("bbbbbbbbbbb", {**sample_result, "video_title": "Video B"})
            assert get_record_count() == 2

    def test_same_video_id_allowed_twice(self, tmp_db, sample_result):
        """Same video can be saved multiple times (repeated analyses)."""
        from storage import get_record_count, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("dQw4w9WgXcQ", sample_result)
            save_analysis("dQw4w9WgXcQ", sample_result)
            assert get_record_count() == 2

    def test_does_not_raise_on_bad_data(self, tmp_db):
        """save_analysis must swallow exceptions gracefully."""
        from storage import save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("vid123456789", {})   # missing most fields — should not raise

    def test_stores_correct_title(self, tmp_db, sample_result):
        from storage import get_history, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("dQw4w9WgXcQ", sample_result)
            records = get_history()
        assert records[0]["video_title"] == sample_result["video_title"]

    def test_stores_correct_comment_count(self, tmp_db, sample_result):
        from storage import get_history, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("dQw4w9WgXcQ", sample_result)
            records = get_history()
        assert records[0]["total_comments"] == 250


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------

class TestGetHistory:
    def test_returns_empty_list_when_no_records(self, tmp_db):
        from storage import get_history
        with patch("storage.DB_PATH", tmp_db):
            assert get_history() == []

    def test_returns_correct_number_of_records(self, tmp_db, sample_result):
        from storage import get_history, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            for i in range(5):
                save_analysis(f"vid{i:011d}", {**sample_result, "video_title": f"Video {i}"})
            records = get_history()
        assert len(records) == 5

    def test_respects_limit(self, tmp_db, sample_result):
        from storage import get_history, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            for i in range(10):
                save_analysis(f"vid{i:011d}", sample_result)
            records = get_history(limit=3)
        assert len(records) == 3

    def test_returns_newest_first(self, tmp_db, sample_result):
        from storage import get_history, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("aaa00000000", {**sample_result, "video_title": "Older"})
            save_analysis("bbb00000000", {**sample_result, "video_title": "Newer"})
            records = get_history()
        assert records[0]["video_title"] == "Newer"
        assert records[1]["video_title"] == "Older"

    def test_sentiment_decoded_from_json(self, tmp_db, sample_result):
        from storage import get_history, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("dQw4w9WgXcQ", sample_result)
            records = get_history()
        assert isinstance(records[0]["overall_sentiment"], dict)
        assert records[0]["overall_sentiment"]["Positive"] == 70.0

    def test_categories_decoded_from_json(self, tmp_db, sample_result):
        from storage import get_history, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("dQw4w9WgXcQ", sample_result)
            records = get_history()
        assert isinstance(records[0]["comment_categories"], dict)

    def test_returns_list_of_dicts(self, tmp_db, sample_result):
        from storage import get_history, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("dQw4w9WgXcQ", sample_result)
            records = get_history()
        assert isinstance(records, list)
        assert isinstance(records[0], dict)

    def test_record_has_required_keys(self, tmp_db, sample_result):
        from storage import get_history, save_analysis
        with patch("storage.DB_PATH", tmp_db):
            save_analysis("dQw4w9WgXcQ", sample_result)
            record = get_history()[0]
        for key in ("id", "video_id", "video_title", "youtube_url",
                    "analysis_method", "total_comments",
                    "overall_sentiment", "comment_categories", "created_at"):
            assert key in record, f"Missing key: {key}"
