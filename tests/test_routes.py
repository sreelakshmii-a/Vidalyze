"""
Flask route integration tests for app.py.

All external calls (YouTube API, Gemini API, cache) are mocked so tests
run offline without real credentials.
"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_categorized(comments, sentiment="Positive", category="Positive"):
    return [{"comment": c, "sentiment": sentiment, "category": category} for c in comments]


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

class TestIndexRoute:
    def test_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_returns_html(self, client):
        response = client.get("/")
        assert b"Vidalyze" in response.data
        assert b"text/html" in response.content_type.encode()


# ---------------------------------------------------------------------------
# POST /analyze — input validation
# ---------------------------------------------------------------------------

class TestAnalyzeValidation:
    def test_empty_url_returns_400(self, client):
        resp = client.post("/analyze", data={"youtube_url": ""})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_missing_url_field_returns_400(self, client):
        resp = client.post("/analyze", data={})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_non_youtube_url_returns_400(self, client):
        resp = client.post("/analyze", data={"youtube_url": "https://google.com/watch?v=abc12345678"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "Invalid" in data["error"] or "invalid" in data["error"]

    def test_random_string_returns_400(self, client):
        resp = client.post("/analyze", data={"youtube_url": "not-a-url"})
        assert resp.status_code == 400

    def test_valid_format_but_api_error_returns_error(self, client):
        with patch("app.build_youtube_service", side_effect=ValueError("No API key")):
            resp = client.post("/analyze", data={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
        assert resp.status_code == 500
        assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# POST /analyze — successful analysis (TextBlob fallback path)
# ---------------------------------------------------------------------------

class TestAnalyzeSuccess:
    _URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def _base_patches(self, comments, categorized):
        """Standard patches for a successful uncached fallback analysis."""
        return [
            patch("app._get_cached", return_value=None),
            patch("app._set_cached"),
            patch("app.build_youtube_service"),
            patch("app.fetch_video_title", return_value="Test Video Title"),
            patch("app.fetch_youtube_comments", return_value=(comments, None)),
            patch("app.GEMINI_API_KEY", ""),
            patch("app.analyze_sentiment_fallback", return_value=categorized),
            patch("app.generate_insights_fallback", return_value="## Summary\n\nGood video."),
        ]

    def test_returns_200_with_valid_data(self, client, sample_comments, sample_categorized):
        p = self._base_patches(sample_comments, sample_categorized)
        with p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7]:
            resp = client.post("/analyze", data={"youtube_url": self._URL})

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["video_title"] == "Test Video Title"
        assert data["total_comments"] == len(sample_comments)
        assert "overall_sentiment" in data
        assert "comment_categories" in data
        assert "comments_data" in data
        assert "overall_insights" in data
        assert "analysis_method" in data

    def test_analysis_method_fallback_when_no_gemini_key(self, client, sample_comments, sample_categorized):
        p = self._base_patches(sample_comments, sample_categorized)
        with p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7]:
            resp = client.post("/analyze", data={"youtube_url": self._URL})
        data = resp.get_json()
        assert "TextBlob" in data["analysis_method"] or "Fallback" in data["analysis_method"]

    def test_comments_data_has_correct_keys(self, client, sample_comments, sample_categorized):
        p = self._base_patches(sample_comments, sample_categorized)
        with p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7]:
            resp = client.post("/analyze", data={"youtube_url": self._URL})
        for item in resp.get_json()["comments_data"]:
            assert "comment" in item
            assert "sentiment" in item
            assert "category" in item

    def test_overall_sentiment_percentages_sum_to_100(self, client, sample_comments, sample_categorized):
        p = self._base_patches(sample_comments, sample_categorized)
        with p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7]:
            resp = client.post("/analyze", data={"youtube_url": self._URL})
        overall = resp.get_json()["overall_sentiment"]
        assert abs(sum(overall.values()) - 100.0) < 0.5

    def test_cached_field_false_on_first_request(self, client, sample_comments, sample_categorized):
        p = self._base_patches(sample_comments, sample_categorized)
        with p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7]:
            resp = client.post("/analyze", data={"youtube_url": self._URL})
        assert resp.get_json()["cached"] is False


# ---------------------------------------------------------------------------
# POST /analyze — error paths
# ---------------------------------------------------------------------------

class TestAnalyzeErrors:
    _URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def test_fetch_error_returns_400(self, client):
        with patch("app._get_cached", return_value=None), \
             patch("app.build_youtube_service"), \
             patch("app.fetch_video_title", return_value="Test Video"), \
             patch("app.fetch_youtube_comments", return_value=([], "Comments are disabled for this video.")):
            resp = client.post("/analyze", data={"youtube_url": self._URL})

        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "disabled" in data["error"].lower()

    def test_no_comments_returns_400(self, client):
        with patch("app._get_cached", return_value=None), \
             patch("app.build_youtube_service"), \
             patch("app.fetch_video_title", return_value="Test Video"), \
             patch("app.fetch_youtube_comments", return_value=([], None)):
            resp = client.post("/analyze", data={"youtube_url": self._URL})

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------

class TestCacheBehaviour:
    def test_second_request_uses_cache(self, client, sample_comments, sample_categorized):
        """When _get_cached returns a result, fetch_youtube_comments must NOT be called."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        cached_result = {
            "video_title": "Cached Video", "cached": True, "total_comments": 10,
            "overall_sentiment": {"Positive": 100.0}, "comment_categories": {"Positive": 10},
            "comments_data": [], "overall_insights": "Great.", "analysis_method": "Gemini",
            "youtube_url": url,
        }

        with patch("app._get_cached", return_value=cached_result), \
             patch("app.fetch_youtube_comments") as mock_fetch:
            resp = client.post("/analyze", data={"youtube_url": url})

        assert resp.status_code == 200
        assert resp.get_json()["cached"] is True
        mock_fetch.assert_not_called()   # cache hit → no fetch

    def test_different_videos_analyzed_independently(self, client, sample_comments, sample_categorized):
        """Two different video IDs must both return 200 and their own data."""
        url1 = "https://www.youtube.com/watch?v=aaaaaaaaaaa"
        url2 = "https://www.youtube.com/watch?v=bbbbbbbbbbb"

        common_patches = [
            patch("app._get_cached", return_value=None),
            patch("app._set_cached"),
            patch("app.build_youtube_service"),
            patch("app.fetch_youtube_comments", return_value=(sample_comments, None)),
            patch("app.GEMINI_API_KEY", ""),
            patch("app.analyze_sentiment_fallback", return_value=sample_categorized),
            patch("app.generate_insights_fallback", return_value="Insights"),
        ]

        with common_patches[0], common_patches[1], common_patches[2], common_patches[3], \
             common_patches[4], common_patches[5], common_patches[6]:
            with patch("app.fetch_video_title", return_value="Video A"):
                r1 = client.post("/analyze", data={"youtube_url": url1})
            with patch("app.fetch_video_title", return_value="Video B"):
                r2 = client.post("/analyze", data={"youtube_url": url2})

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.get_json()["video_title"] == "Video A"
        assert r2.get_json()["video_title"] == "Video B"


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

class TestErrorHandlers:
    def test_404_returns_json_or_html(self, client):
        resp = client.get("/nonexistent-route")
        assert resp.status_code == 404
