"""
Shared pytest fixtures for Vidalyze tests.
"""
import os
import sys
from unittest.mock import MagicMock

import pytest

# Project root on sys.path so imports resolve regardless of cwd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Patch API keys in the environment BEFORE any project module is imported.
# This ensures config.py reads "test-yt-key" instead of None.
os.environ.setdefault("YOUTUBE_API_KEY", "test-yt-key")
os.environ.setdefault("GEMINI_API_KEY", "")   # empty → TextBlob fallback path


@pytest.fixture(scope="session")
def app():
    """
    Flask app configured for the test session.
    Rate limiting is disabled by patching _check_request_limit so individual
    tests don't exhaust the 5/min quota against each other.
    """
    from app import app as flask_app
    from app import limiter

    flask_app.config["TESTING"] = True
    flask_app.config["RATELIMIT_ENABLED"] = False  # belt
    flask_app.config["WTF_CSRF_ENABLED"] = False

    # Suspenders: directly neutralise the rate-limit check regardless of
    # Flask-Limiter version or config-key naming conventions.
    limiter._check_request_limit = lambda *a, **kw: None

    return flask_app


@pytest.fixture
def client(app):
    """Fresh Flask test client for each test."""
    with app.test_client() as c:
        yield c


@pytest.fixture
def sample_comments():
    """Representative set of YouTube-style comments."""
    return [
        "This video is absolutely amazing, thank you so much!",
        "I hate this content, it is terrible and the worst.",
        "Can you please suggest more topics and improve the examples?",
        "I have a problem — how do I fix this bug in the code?",
        "Just watched it. Pretty okay overall.",
        "Great job! Love this channel.",
        "Disappointed with the quality, this is bad.",
        "Could you add more examples in the next video?",
        "Neutral comment without strong feeling.",
        "What a brilliant tutorial, keep it up!",
    ]


@pytest.fixture
def sample_categorized(sample_comments):
    """Pre-built categorized comment list (TextBlob fallback style)."""
    return [
        {"comment": sample_comments[0], "sentiment": "Positive",  "category": "Positive"},
        {"comment": sample_comments[1], "sentiment": "Negative",  "category": "Negative"},
        {"comment": sample_comments[2], "sentiment": "Neutral",   "category": "Suggestion"},
        {"comment": sample_comments[3], "sentiment": "Neutral",   "category": "Help"},
        {"comment": sample_comments[4], "sentiment": "Neutral",   "category": "Neutral/Other"},
        {"comment": sample_comments[5], "sentiment": "Positive",  "category": "Positive"},
        {"comment": sample_comments[6], "sentiment": "Negative",  "category": "Negative"},
        {"comment": sample_comments[7], "sentiment": "Neutral",   "category": "Suggestion"},
        {"comment": sample_comments[8], "sentiment": "Neutral",   "category": "Neutral/Other"},
        {"comment": sample_comments[9], "sentiment": "Positive",  "category": "Positive"},
    ]


@pytest.fixture
def mock_youtube_service():
    """Mock googleapiclient YouTube service with 5 stub comments."""
    service = MagicMock()
    service.videos().list().execute.return_value = {
        "items": [{"snippet": {"title": "Mock Video Title"}}]
    }
    service.commentThreads().list().execute.return_value = {
        "items": [
            {"snippet": {"topLevelComment": {"snippet": {"textDisplay": f"Comment {i}"}}}}
            for i in range(5)
        ],
        "nextPageToken": None,
    }
    return service
