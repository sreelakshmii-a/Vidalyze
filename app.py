import logging
import os
import re
import threading

from cachetools import TTLCache
from flask import Flask, jsonify, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import CACHE_MAX_SIZE, CACHE_TTL_SECONDS, GEMINI_API_KEY
from gemini import (
    GeminiQuotaError,
    analyze_sentiment_gemini,
    generate_highlights_gemini,
    generate_insights_gemini,
)
from sentiment import (
    analyze_sentiment_fallback,
    compute_sentiment_timeline,
    compute_stats,
    compute_word_frequencies,
    generate_insights_fallback,
)
from storage import get_history, init_db, save_analysis
from youtube import build_youtube_service, fetch_video_title, fetch_youtube_comments, get_video_id

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _get_session_id() -> str:
    """Read and validate the X-Session-Id request header.
    Returns the UUID string if valid, empty string otherwise.
    """
    sid = request.headers.get("X-Session-Id", "").strip()
    return sid if _UUID_RE.match(sid) else ""

logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Rate limiting — 5 analysis requests per minute per IP
# ---------------------------------------------------------------------------
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

# ---------------------------------------------------------------------------
# In-memory analysis cache — keyed by video_id, 1-hour TTL
# ---------------------------------------------------------------------------
_cache: TTLCache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL_SECONDS)
_cache_lock = threading.Lock()


def _get_cached(video_id: str) -> dict | None:
    with _cache_lock:
        return _cache.get(video_id)


def _set_cached(video_id: str, result: dict) -> None:
    with _cache_lock:
        _cache[video_id] = result


# ---------------------------------------------------------------------------
# Database — initialise on startup
# ---------------------------------------------------------------------------
with app.app_context():
    init_db()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/history", methods=["GET"])
def history():
    """Returns the 20 most recent analyses for the requesting session."""
    records = get_history(limit=20, session_id=_get_session_id())
    return jsonify(records)


@app.route("/analyze", methods=["POST"])
@limiter.limit("5 per minute")
def analyze():
    """
    Fetches YouTube comments, runs sentiment analysis (Gemini preferred,
    TextBlob fallback), and returns structured JSON for the frontend.

    Results are cached in memory by video_id (1-hour TTL) and persisted
    to SQLite for the history panel.
    """
    session_id  = _get_session_id()
    youtube_url = request.form.get("youtube_url", "").strip()

    if not youtube_url:
        return jsonify({"error": "YouTube URL is required."}), 400

    video_id = get_video_id(youtube_url)
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL. Please check the format and try again."}), 400

    # Return cached result if available (avoids redundant API calls).
    # Still record in this user's history so their sidebar stays accurate.
    cached = _get_cached(video_id)
    if cached:
        logger.info("Cache hit for video %s.", video_id)
        save_analysis(video_id, cached, session_id)
        cached["cached"] = True
        return jsonify(cached)

    # Build YouTube service — fail fast if key is missing
    try:
        youtube_service = build_youtube_service()
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception:
        logger.exception("Failed to initialize YouTube API service")
        return jsonify({"error": "Failed to connect to YouTube API. Check your YOUTUBE_API_KEY."}), 500

    video_title = fetch_video_title(youtube_service, video_id)

    comments, fetch_error = fetch_youtube_comments(video_id)
    if fetch_error:
        return jsonify({"error": fetch_error, "video_title": video_title}), 400
    if not comments:
        return jsonify({"error": "No comments found for this video.", "video_title": video_title}), 400

    # --- Analysis ---
    categorized_comments: list[dict] = []
    overall_insights = ""
    analysis_method = "TextBlob/Rule-Based Fallback"
    highlights: dict = {"top_insights": [], "top_complaints": [], "feature_requests": []}

    if GEMINI_API_KEY:
        try:
            logger.info("Attempting Gemini analysis for video %s...", video_id)
            categorized_comments = analyze_sentiment_gemini(comments)
            if categorized_comments:
                overall_insights = generate_insights_gemini(categorized_comments)
                highlights = generate_highlights_gemini(categorized_comments)
                analysis_method = "Gemini"
                logger.info("Gemini analysis successful for video %s.", video_id)
            else:
                logger.warning("Gemini returned no results; falling back to TextBlob.")
                analysis_method = "TextBlob Fallback (Gemini returned no results)"
        except GeminiQuotaError as e:
            logger.warning("Gemini quota exceeded for video %s: %s", video_id, e)
            analysis_method = "TextBlob Fallback (Gemini quota exceeded — see README)"
        except Exception:
            logger.exception("Gemini analysis failed; falling back to TextBlob.")
            analysis_method = "TextBlob Fallback (Gemini error)"

    if analysis_method != "Gemini":
        logger.info("Running TextBlob fallback for video %s.", video_id)
        categorized_comments = analyze_sentiment_fallback(comments)
        overall_insights = generate_insights_fallback(categorized_comments)

    overall_sentiment, comment_categories = compute_stats(categorized_comments)

    result = {
        "youtube_url":         youtube_url,
        "video_title":         video_title,
        "total_comments":      len(comments),
        "overall_sentiment":   overall_sentiment,
        "comment_categories":  comment_categories,
        "comments_data":       categorized_comments,
        "overall_insights":    overall_insights,
        "highlights":          highlights,
        "analysis_method":     analysis_method,
        "word_frequencies":    compute_word_frequencies(categorized_comments),
        "sentiment_over_time": compute_sentiment_timeline(categorized_comments),
        "cached":              False,
    }

    _set_cached(video_id, result)
    save_analysis(video_id, result, session_id)   # persist summary to SQLite
    return jsonify(result)


@app.errorhandler(429)
def rate_limit_exceeded(e):
    return jsonify({"error": "Too many requests. Please wait a minute and try again."}), 429


@app.errorhandler(500)
def internal_error(e):
    logger.error("Unhandled server error: %s", e)
    return jsonify({"error": "An internal server error occurred."}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)
