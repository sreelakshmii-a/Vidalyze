import logging
import re

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import (
    MAX_COMMENTS,
    YOUTUBE_API_KEY,
    YOUTUBE_API_SERVICE_NAME,
    YOUTUBE_API_VERSION,
)

logger = logging.getLogger(__name__)

_URL_PATTERNS = [
    r"(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)/(?:watch\?v=|embed/|v/|)([\w-]{11})(?:\S+)?",
    r"(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)/shorts/([\w-]{11})(?:\S+)?",
]

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "www.youtu.be"}


def get_video_id(url: str) -> str | None:
    """Extracts the 11-character video ID from any YouTube URL format."""
    if not url:
        logger.warning("Empty URL passed to get_video_id.")
        return None

    # Reject URLs that aren't from YouTube at all
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url if url.startswith("http") else f"https://{url}")
        if parsed.netloc and parsed.netloc not in _YOUTUBE_HOSTS:
            logger.warning("Non-YouTube host rejected: %s", parsed.netloc)
            return None
    except Exception:
        pass

    for pattern in _URL_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    logger.warning("Could not extract video ID from URL: %s", url)
    return None


def build_youtube_service():
    """Builds and returns an authenticated YouTube API service client."""
    if not YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY is not set in environment variables.")
    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=YOUTUBE_API_KEY)


def fetch_video_title(youtube_service, video_id: str) -> str:
    """Returns the video title, or a fallback string on any error."""
    try:
        response = youtube_service.videos().list(part="snippet", id=video_id).execute()
        items = response.get("items", [])
        if items:
            return items[0]["snippet"]["title"]
        return "Video Details Unavailable"
    except HttpError as e:
        logger.error("HttpError fetching video title (status %s): %s", e.resp.status, e)
        return f"Title fetch failed (status {e.resp.status})"
    except Exception:
        logger.exception("Unexpected error fetching video title for %s", video_id)
        return "Title Unavailable"


def fetch_youtube_comments(video_id: str, max_results: int = MAX_COMMENTS) -> tuple[list[str], str | None]:
    """
    Fetches up to max_results top-level comments for the given video.

    Returns:
        (comments, None)  on success
        ([], error_msg)   on failure
    """
    if not video_id:
        return [], "Video ID is missing."
    if not YOUTUBE_API_KEY:
        return [], "YouTube API key is not configured. Set YOUTUBE_API_KEY in your .env file."

    try:
        youtube = build_youtube_service()
    except ValueError as e:
        return [], str(e)
    except Exception as e:
        return [], f"Failed to initialize YouTube service: {e}"

    comments: list[str] = []
    next_page_token = None
    logger.info("Fetching comments for video %s (max %d)...", video_id, max_results)

    try:
        while len(comments) < max_results:
            api_request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                textFormat="plainText",
                maxResults=min(max_results - len(comments), 100),
                pageToken=next_page_token,
            )
            response = api_request.execute()

            for item in response.get("items", []):
                text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                comments.append(text)
                if len(comments) >= max_results:
                    break

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

            logger.info("Fetched %d comments so far...", len(comments))

    except HttpError as e:
        details = e.error_details[0] if e.error_details else {}
        reason = details.get("reason", "")
        message = details.get("message", "")
        logger.error("YouTube API HttpError: %s", e)

        if e.resp.status == 403:
            if reason == "commentsDisabled":
                return [], "Comments are disabled for this video by the creator."
            if reason == "quotaExceeded" or "dailyLimitExceeded" in message:
                return [], "YouTube API quota exceeded. Please try again later."
            return [], f"YouTube access denied (403): {message or 'Unknown reason.'}"
        if e.resp.status == 404:
            return [], "Video not found. Please check the URL."
        return [], f"YouTube API error (status {e.resp.status}): {message or 'No details.'}"

    except Exception:
        logger.exception("Unexpected error fetching comments for %s", video_id)
        return [], "An unexpected error occurred while fetching comments."

    logger.info("Fetched %d comments for video %s.", len(comments), video_id)
    return comments, None
