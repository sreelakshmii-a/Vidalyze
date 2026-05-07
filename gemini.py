"""
Gemini API client for Vidalyze.

Sentiment analysis sends all 500 comments in ONE request using an index-based
response schema.  This avoids echoing comment text back in the output, which
keeps output tokens to ~5,000 (well within the 8,192 limit per call).

Token budget for 500 comments (worst-case 200 chars each):
  INPUT:  ~25,000 tokens  ← limit is 1,000,000  ✓
  OUTPUT: ~5,000  tokens  ← limit is 8,192       ✓

On Windows, WindowsSelectorEventLoopPolicy prevents the
"RuntimeError: Event loop is closed" noise from ProactorEventLoop cleanup.
"""

import asyncio
import json
import logging
import sys

import aiohttp

from config import GEMINI_API_KEY, GEMINI_API_URL

logger = logging.getLogger(__name__)

# Fix Windows ProactorEventLoop cleanup noise
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------

class GeminiQuotaError(Exception):
    """Raised when Gemini returns HTTP 429 (rate or daily quota exceeded)."""


# ---------------------------------------------------------------------------
# Valid values
# ---------------------------------------------------------------------------

_VALID_SENTIMENTS = {"Positive", "Neutral", "Negative", "Mixed"}


# ---------------------------------------------------------------------------
# JSON schema definitions
# ---------------------------------------------------------------------------

# Index-only: model returns position + label, NOT the full comment text.
# This keeps output tokens at ~10 per comment (vs ~30+ when echoing text).
_SENTIMENT_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "index": {
                "type": "INTEGER",
                "description": "0-based position of the comment in the input list.",
            },
            "sentiment": {
                "type": "STRING",
                "enum": ["Positive", "Neutral", "Negative", "Mixed"],
                "description": "Sentiment classification.",
            },
        },
        "required": ["index", "sentiment"],
    },
}

_HIGHLIGHTS_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "top_insights":    {"type": "ARRAY", "items": {"type": "STRING"},
                            "description": "5 most insightful or thought-provoking comments."},
        "top_complaints":  {"type": "ARRAY", "items": {"type": "STRING"},
                            "description": "5 most common complaints or criticisms."},
        "feature_requests": {"type": "ARRAY", "items": {"type": "STRING"},
                             "description": "5 most requested features or improvements."},
    },
    "required": ["top_insights", "top_complaints", "feature_requests"],
}


# ---------------------------------------------------------------------------
# Core async helper
# ---------------------------------------------------------------------------

async def _call_gemini(prompt: str, api_key: str, schema=None) -> list | str | None:
    """
    Makes one async call to the Gemini API.

    Raises GeminiQuotaError on HTTP 429.
    Returns parsed JSON when schema is provided, plain text otherwise, None on failure.
    """
    url = f"{GEMINI_API_URL}?key={api_key}"
    payload: dict = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    if schema:
        payload["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseSchema": schema,
        }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 429:
                    body = await resp.json(content_type=None)
                    msg = body.get("error", {}).get("message", "Quota exceeded")
                    raise GeminiQuotaError(msg)

                resp.raise_for_status()
                result = await resp.json()

        candidates = result.get("candidates", [])
        if not candidates:
            logger.warning("Gemini returned no candidates.")
            return None

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            logger.warning("Gemini candidate has no parts.")
            return None

        text = parts[0]["text"]
        if schema:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                logger.error("Gemini returned invalid JSON: %.200s", text)
                return None
        return text

    except GeminiQuotaError:
        raise  # always propagate so app.py can show a clear message
    except aiohttp.ClientResponseError as e:
        logger.error("Gemini HTTP error %s: %s", e.status, e.message)
        return None
    except aiohttp.ClientError as e:
        logger.error("Gemini network error: %s", e)
        return None
    except Exception:
        logger.exception("Unexpected error calling Gemini API")
        return None


# ---------------------------------------------------------------------------
# Sentiment analysis — ONE request for all comments
# ---------------------------------------------------------------------------

async def _analyze_sentiment_async(comments: list[str], api_key: str) -> list[dict]:
    """
    Classifies sentiment for all comments in a single Gemini request.

    Uses an index-based schema so the model returns only (index, sentiment)
    pairs — not the full comment text — keeping output tokens to ~5,000 for
    500 comments, well within Gemini's 8,192-token output limit.

    Any comment whose index is missing from the response defaults to Neutral.
    Raises GeminiQuotaError if quota is exceeded.
    """
    if not comments:
        return []

    # Pass comments as a JSON array; the model uses 0-based array position as index.
    prompt = (
        f"Classify each YouTube comment's sentiment as Positive, Neutral, Negative, or Mixed.\n"
        f"There are {len(comments)} comments (0-indexed).\n"
        f"Return a JSON array where every object has:\n"
        f"  - 'index': the 0-based position of the comment\n"
        f"  - 'sentiment': one of Positive | Neutral | Negative | Mixed\n"
        f"Classify ALL {len(comments)} comments. Do not skip any.\n\n"
        f"Comments:\n{json.dumps(comments, ensure_ascii=False)}"
    )

    logger.info("Sending all %d comments to Gemini in one request…", len(comments))
    result = await _call_gemini(prompt, api_key, _SENTIMENT_SCHEMA)

    if not isinstance(result, list):
        logger.warning("Gemini sentiment response was not a list (got %s).", type(result).__name__)
        return []

    # Build index → sentiment map; validate every entry
    sentiment_map: dict[int, str] = {}
    for item in result:
        idx       = item.get("index")
        sentiment = item.get("sentiment", "Neutral")
        if sentiment not in _VALID_SENTIMENTS:
            sentiment = "Neutral"
        if isinstance(idx, int) and 0 <= idx < len(comments):
            sentiment_map[idx] = sentiment

    classified = len(sentiment_map)
    total      = len(comments)
    if classified < total:
        logger.warning("Gemini classified %d/%d comments; %d defaulted to Neutral.",
                       classified, total, total - classified)
    else:
        logger.info("Gemini classified all %d comments.", total)

    # Reconstruct in original order; default missing indices to Neutral
    return [
        {
            "comment":  comments[i],
            "sentiment": sentiment_map.get(i, "Neutral"),
            "category":  sentiment_map.get(i, "Neutral"),
        }
        for i in range(total)
    ]


# ---------------------------------------------------------------------------
# Insights summary — single request
# ---------------------------------------------------------------------------

async def _generate_insights_async(categorized_comments: list[dict], api_key: str) -> str:
    """Generates a markdown insight summary from categorized comments."""
    groups: dict[str, list[str]] = {s: [] for s in _VALID_SENTIMENTS}
    for item in categorized_comments:
        groups.get(item["sentiment"], groups["Neutral"]).append(item["comment"])

    def fmt(label: str) -> str:
        samples = groups[label][:5]
        return "\n".join(f"- {c}" for c in samples) if samples else f"No {label.lower()} comments."

    prompt = f"""
Based on the following categorized YouTube comments, provide an overall summary of audience
sentiment and actionable insights for the video creator.

Positive Comments ({len(groups['Positive'])} total):
{fmt('Positive')}

Neutral Comments ({len(groups['Neutral'])} total):
{fmt('Neutral')}

Negative Comments ({len(groups['Negative'])} total):
{fmt('Negative')}

Mixed Comments ({len(groups['Mixed'])} total):
{fmt('Mixed')}

Overall — Positive: {len(groups['Positive'])}, Neutral: {len(groups['Neutral'])}, \
Negative: {len(groups['Negative'])}, Mixed: {len(groups['Mixed'])}

Respond in Markdown. Be concise and actionable.
"""
    result = await _call_gemini(prompt, api_key)
    return result if isinstance(result, str) else "Could not generate insights from Gemini."


# ---------------------------------------------------------------------------
# Highlights extraction — single request
# ---------------------------------------------------------------------------

async def _generate_highlights_async(
    categorized_comments: list[dict], api_key: str
) -> dict:
    """Extracts top insights, complaints, and feature requests from comments."""
    # Cap at 200 comments to stay well inside the context window
    sample = [c["comment"] for c in categorized_comments[:200]]

    prompt = (
        "Analyze the following YouTube video comments and return exactly three lists:\n\n"
        "1. top_insights      — the 5 most insightful, interesting, or genuinely valuable comments.\n"
        "2. top_complaints    — the 5 most common complaints or criticisms (paraphrase recurring themes).\n"
        "3. feature_requests  — the 5 most requested features or improvements.\n\n"
        "Return empty arrays where there are fewer than 5 relevant comments. "
        "Only use content from the provided comments.\n\n"
        f"Comments:\n{json.dumps(sample, ensure_ascii=False)}"
    )

    result = await _call_gemini(prompt, api_key, _HIGHLIGHTS_SCHEMA)
    empty: dict = {"top_insights": [], "top_complaints": [], "feature_requests": []}

    if not isinstance(result, dict):
        return empty

    return {
        "top_insights":     result.get("top_insights",     [])[:5],
        "top_complaints":   result.get("top_complaints",   [])[:5],
        "feature_requests": result.get("feature_requests", [])[:5],
    }


# ---------------------------------------------------------------------------
# Public sync API  (called from Flask routes via asyncio.run)
# ---------------------------------------------------------------------------

def analyze_sentiment_gemini(
    comments: list[str], api_key: str = GEMINI_API_KEY
) -> list[dict]:
    """
    Classifies sentiment for all comments in one Gemini call.
    Raises GeminiQuotaError if quota is exhausted.
    Returns [] if no API key is configured.
    """
    if not api_key:
        logger.info("No Gemini API key — skipping sentiment analysis.")
        return []
    return asyncio.run(_analyze_sentiment_async(comments, api_key))


def generate_insights_gemini(
    categorized_comments: list[dict], api_key: str = GEMINI_API_KEY
) -> str:
    """
    Generates markdown insights in one Gemini call.
    Raises GeminiQuotaError if quota is exhausted.
    """
    if not categorized_comments:
        return "No comments available to generate insights."
    if not api_key:
        logger.info("No Gemini API key — skipping insights generation.")
        return "Insights unavailable (Gemini API key not configured)."
    return asyncio.run(_generate_insights_async(categorized_comments, api_key))


def generate_highlights_gemini(
    categorized_comments: list[dict], api_key: str = GEMINI_API_KEY
) -> dict:
    """
    Extracts comment highlights in one Gemini call.
    Returns empty lists silently if quota is exhausted (highlights are non-critical).
    """
    empty = {"top_insights": [], "top_complaints": [], "feature_requests": []}
    if not categorized_comments or not api_key:
        return empty
    try:
        return asyncio.run(_generate_highlights_async(categorized_comments, api_key))
    except GeminiQuotaError:
        logger.warning("Gemini quota exhausted during highlights — returning empty.")
        return empty
