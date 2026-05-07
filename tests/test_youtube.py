"""
Tests for youtube.py — URL extraction and comment fetching.
"""
import os
import sys
from unittest.mock import MagicMock, patch

from googleapiclient.errors import HttpError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from youtube import fetch_video_title, fetch_youtube_comments, get_video_id

# ---------------------------------------------------------------------------
# get_video_id
# ---------------------------------------------------------------------------

class TestGetVideoId:
    """All common YouTube URL formats must resolve to the 11-char video ID."""

    def test_standard_watch_url(self):
        assert get_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_standard_watch_url_no_www(self):
        assert get_video_id("https://youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_youtu_be_short_url(self):
        assert get_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_youtu_be_no_scheme(self):
        assert get_video_id("youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_embed_url(self):
        assert get_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_shorts_url(self):
        assert get_video_id("https://www.youtube.com/shorts/abc12345678") == "abc12345678"

    def test_url_with_extra_params(self):
        assert get_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s&list=PLtest") == "dQw4w9WgXcQ"

    def test_url_with_timestamp(self):
        assert get_video_id("https://youtu.be/dQw4w9WgXcQ?t=99") == "dQw4w9WgXcQ"

    def test_invalid_non_youtube_host(self):
        assert get_video_id("https://notyoutube.com/watch?v=dQw4w9WgXcQ") is None

    def test_empty_string(self):
        assert get_video_id("") is None

    def test_none_input(self):
        assert get_video_id(None) is None

    def test_random_string(self):
        assert get_video_id("not-a-url-at-all") is None

    def test_malformed_url(self):
        assert get_video_id("http://") is None

    def test_video_id_exactly_11_chars(self):
        vid = get_video_id("https://www.youtube.com/watch?v=12345678901")
        assert vid == "12345678901"
        assert len(vid) == 11


# ---------------------------------------------------------------------------
# fetch_video_title
# ---------------------------------------------------------------------------

class TestFetchVideoTitle:
    def test_returns_title_on_success(self, mock_youtube_service):
        title = fetch_video_title(mock_youtube_service, "dQw4w9WgXcQ")
        assert title == "Mock Video Title"

    def test_returns_fallback_when_no_items(self):
        svc = MagicMock()
        svc.videos().list().execute.return_value = {"items": []}
        result = fetch_video_title(svc, "dQw4w9WgXcQ")
        assert "Unavailable" in result

    def test_returns_fallback_on_http_error(self):
        svc = MagicMock()
        resp = MagicMock()
        resp.status = 403
        svc.videos().list().execute.side_effect = HttpError(resp=resp, content=b"Forbidden")
        result = fetch_video_title(svc, "dQw4w9WgXcQ")
        assert "403" in result or "failed" in result.lower()

    def test_returns_fallback_on_generic_exception(self):
        svc = MagicMock()
        svc.videos().list().execute.side_effect = RuntimeError("boom")
        result = fetch_video_title(svc, "dQw4w9WgXcQ")
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# fetch_youtube_comments
# ---------------------------------------------------------------------------

_KEY_PATCH = patch("youtube.YOUTUBE_API_KEY", "test-yt-key")


class TestFetchYoutubeComments:
    def test_returns_comments_on_success(self, mock_youtube_service):
        with _KEY_PATCH, patch("youtube.build_youtube_service", return_value=mock_youtube_service):
            comments, error = fetch_youtube_comments("dQw4w9WgXcQ")
        assert error is None
        assert len(comments) == 5
        assert all(isinstance(c, str) for c in comments)

    def test_returns_error_for_empty_video_id(self):
        with _KEY_PATCH:
            comments, error = fetch_youtube_comments("")
        assert comments == []
        assert error is not None
        assert "missing" in error.lower() or "Video ID" in error

    def test_returns_error_when_comments_disabled(self, mock_youtube_service):
        resp = MagicMock()
        resp.status = 403
        err = HttpError(
            resp=resp,
            content=b'{"error":{"errors":[{"reason":"commentsDisabled","message":"disabled"}]}}'
        )
        err.error_details = [{"reason": "commentsDisabled", "message": "disabled"}]
        mock_youtube_service.commentThreads().list().execute.side_effect = err

        with _KEY_PATCH, patch("youtube.build_youtube_service", return_value=mock_youtube_service):
            comments, error = fetch_youtube_comments("dQw4w9WgXcQ")

        assert comments == []
        assert "disabled" in error.lower()

    def test_returns_error_when_video_not_found(self, mock_youtube_service):
        resp = MagicMock()
        resp.status = 404
        err = HttpError(resp=resp, content=b"Not Found")
        err.error_details = []
        mock_youtube_service.commentThreads().list().execute.side_effect = err

        with _KEY_PATCH, patch("youtube.build_youtube_service", return_value=mock_youtube_service):
            comments, error = fetch_youtube_comments("nonexistent123")

        assert comments == []
        assert "not found" in error.lower()

    def test_returns_error_on_quota_exceeded(self, mock_youtube_service):
        resp = MagicMock()
        resp.status = 403
        err = HttpError(resp=resp, content=b"Quota exceeded")
        err.error_details = [{"reason": "quotaExceeded", "message": "Quota exceeded"}]
        mock_youtube_service.commentThreads().list().execute.side_effect = err

        with _KEY_PATCH, patch("youtube.build_youtube_service", return_value=mock_youtube_service):
            comments, error = fetch_youtube_comments("dQw4w9WgXcQ")

        assert comments == []
        assert "quota" in error.lower()

    def test_stops_at_max_results(self):
        """Should not fetch more than max_results comments."""
        svc = MagicMock()
        svc.commentThreads().list().execute.return_value = {
            "items": [
                {"snippet": {"topLevelComment": {"snippet": {"textDisplay": f"c{i}"}}}}
                for i in range(100)
            ],
            "nextPageToken": None,
        }
        with _KEY_PATCH, patch("youtube.build_youtube_service", return_value=svc):
            comments, error = fetch_youtube_comments("vid123456789", max_results=10)

        assert error is None
        assert len(comments) == 10
