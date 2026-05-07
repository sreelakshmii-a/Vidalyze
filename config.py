import logging
import os

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# API keys — loaded from .env, never hardcoded
YOUTUBE_API_KEY: str | None = os.environ.get("YOUTUBE_API_KEY")
GEMINI_API_KEY: str | None = os.environ.get("GEMINI_API_KEY")

# YouTube Data API
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# Analysis tuning
MAX_COMMENTS = 500  # YouTube comments fetched per analysis

# TextBlob polarity thresholds — calibrated: >0.1 = Positive, <-0.1 = Negative
TEXTBLOB_POSITIVE_THRESHOLD = 0.1
TEXTBLOB_NEGATIVE_THRESHOLD = -0.1

# In-memory cache settings
CACHE_TTL_SECONDS = 3600   # 1 hour
CACHE_MAX_SIZE = 100       # max video IDs cached simultaneously

# Gemini model endpoint
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)
