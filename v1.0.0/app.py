import os
import re
from collections import Counter
import pandas as pd
from flask import Flask, render_template, request, jsonify
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Import load_dotenv from dotenv
from dotenv import load_dotenv

# TextBlob for sentiment analysis
from textblob import TextBlob

# Load environment variables from .env file.
# This should be one of the first things you do in your script.
load_dotenv()

# --- Configuration ---
# Get API key from environment variable.
# IMPORTANT: Never hardcode API keys in production!
API_KEY = os.getenv("YOUTUBE_API_KEY")

YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

app = Flask(__name__)

# Essential check: Ensure the API key was loaded
if not API_KEY:
    print("Error: YOUTUBE_API_KEY not found in environment variables or .env file.")
    print("Please create a .env file in the same directory as app.py with: YOUTUBE_API_KEY=\"YOUR_ACTUAL_KEY\"")
    # Using sys.exit() to stop execution gracefully if API key is missing
    import sys
    sys.exit("Exiting: API key is missing. Cannot proceed without it.")

# --- YouTube Comment Extraction Functions ---
def get_video_id_from_url(url):
    """Extracts the video ID from a YouTube URL."""
    pattern = r"(?:https?://)?(?:www\.)?(?:m\.)?(?:youtube\.com|youtu\.be)/(?:watch\?v=|embed/|v/|)([\w-]{11})(?:\S+)?"
    match = re.match(pattern, url)
    if match:
        return match.group(1)
    return None

def get_youtube_comments(video_id, youtube_service, max_results=200):
    """
    Fetches top-level comments for a given YouTube video ID.
    Returns comments list and an error message (or None if no error).
    """
    comments = []
    next_page_token = None
    fetched_count = 0

    while fetched_count < max_results:
        try:
            request = youtube_service.commentThreads().list(
                part="snippet",
                videoId=video_id,
                textFormat="plainText",
                maxResults=min(max_results - fetched_count, 100),  # Max 100 per request
                pageToken=next_page_token
            )
            response = request.execute()

            for item in response["items"]:
                comment_text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                comments.append(comment_text)
                fetched_count += 1
                if fetched_count >= max_results:
                    break

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break # No more pages
        except HttpError as e:
            # Parse the error for specific reasons
            error_details = e.error_details[0] if e.error_details else {}
            reason = error_details.get('reason')
            message = error_details.get('message')

            print(f"YouTube API Error: {e}") # Log the full error for debugging

            if e.resp.status == 403:
                if reason == 'commentsDisabled':
                    return [], "Comments are disabled for this video by the creator."
                elif reason == 'quotaExceeded' or 'dailyLimitExceeded' in str(message): # Cast message to string for 'in' check
                    return [], "API Quota Exceeded or Daily Limit Reached. Please try again later."
                else:
                    return [], f"Access Denied (403): {message or 'Unknown reason.'}"
            elif e.resp.status == 404:
                return [], "Video not found. Please check the video URL."
            else:
                return [], f"An unexpected API error occurred (Status {e.resp.status}): {message or 'No specific message.'}"
        except Exception as e:
            # Catch any other unexpected errors during the process
            print(f"An unexpected error occurred: {e}")
            return [], f"An unexpected error occurred: {e}"

    return comments, None # Return comments list and no error message if successful

# --- 2. Sentiment Analysis ---
def get_sentiment(text):
    """
    Analyzes the sentiment of the given text using TextBlob.
    Returns 'Positive', 'Negative', or 'Neutral'.
    """
    analysis = TextBlob(text)
    if analysis.sentiment.polarity > 0.1: # Slightly adjust threshold for clearer positivity
        return "Positive"
    elif analysis.sentiment.polarity < -0.1: # Slightly adjust threshold for clearer negativity
        return "Negative"
    else:
        return "Neutral"

# --- 3. Comment Categorization (Rule-Based Example) ---
def categorize_comment(comment):
    """
    Categorizes a comment based on keywords.
    This is a basic rule-based approach. For more accuracy,
    you'd typically use trained machine learning models.
    """
    comment_lower = comment.lower()

    # Specific categories first
    if any(word in comment_lower for word in ["suggestion", "suggest", "improve", "add", "consider", "feature", "ideas"]):
        return "Suggestion"
    elif any(word in comment_lower for word in ["help", "trouble", "issue", "fix", "bug", "question", "how to", "problem"]):
        return "Help"
    elif any(word in comment_lower for word in ["thank", "awesome", "great", "love", "amazing", "best", "good"]):
        return "Positive" # Explicitly positive words
    elif any(word in comment_lower for word in ["bad", "hate", "terrible", "worst", "dislike", "cringe"]):
        return "Negative" # Explicitly negative words
    else:
        # Fallback to TextBlob sentiment for less specific comments
        sentiment = get_sentiment(comment)
        if sentiment == "Positive":
            return "Positive"
        elif sentiment == "Negative":
            return "Negative"
        else:
            return "Neutral/Other"

# --- Flask Routes ---
@app.route('/', methods=['GET'])
def index():
    """Renders the main page with the input form."""
    return render_template('index.html')

# This is the @app.route and def analyze() that was previously incorrectly indented.
# Make sure it starts at the very left margin, just like @app.route('/') and def index().
@app.route('/analyze', methods=['POST'])
def analyze():
    youtube_url = request.form['youtube_url']
    video_id = get_video_id_from_url(youtube_url)

    if not video_id:
        return render_template('index.html', error="Invalid YouTube URL provided. Please check the format.")

    youtube_service = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)

    # --- START OF MODIFIED SECTION TO GET VIDEO TITLE ---
    video_title = "Video Title Not Found" # Default title in case of error
    try:
        video_request = youtube_service.videos().list(
            part="snippet",
            id=video_id
        )
        video_response = video_request.execute()

        if video_response and 'items' in video_response and len(video_response['items']) > 0:
            video_title = video_response['items'][0]['snippet']['title']
        else:
            # If video not found via videos().list, it might be private/deleted or ID is wrong
            # The comments fetch might also fail later, but we provide a specific title
            video_title = "Video Details Unavailable"

    except HttpError as e:
        print(f"Error fetching video title: {e}")
        video_title = f"Error fetching title ({e.resp.status})"
        # Decide if you want to fail early or continue to try fetching comments
        # For now, we'll continue, but the title will reflect the error.
    except Exception as e:
        print(f"An unexpected error occurred while fetching video title: {e}")
        video_title = "Error fetching title"
    # --- END OF MODIFIED SECTION TO GET VIDEO TITLE ---


    # Fetch comments and handle potential errors during fetch
    comments, fetch_error = get_youtube_comments(video_id, youtube_service, max_results=500) # Fetch up to 500 comments

    if fetch_error:
        # Pass video_title here as well, so it displays even if comment fetch fails
        return render_template('index.html', error=fetch_error, youtube_url=youtube_url, video_title=video_title)

    if not comments:
        # Pass video_title here as well
        return render_template('index.html', error="No comments found for this video or comments are disabled.", youtube_url=youtube_url, video_title=video_title)

    processed_comments = []
    for comment_text in comments:
        sentiment = get_sentiment(comment_text)
        category = categorize_comment(comment_text)
        processed_comments.append({
            "comment": comment_text,
            "sentiment": sentiment,
            "category": category
        })

    df = pd.DataFrame(processed_comments)

    # --- Generate Summary ---
    overall_sentiment = (df["sentiment"].value_counts(normalize=True) * 100).round(2).to_dict()
    comment_categories = df["category"].value_counts().to_dict()

    # Prepare comments for display (e.g., limit length for table)
    comments_for_display = df.to_dict(orient='records')
    for c in comments_for_display:
        c['comment_preview'] = c['comment'] if len(c['comment']) < 150 else c['comment'][:147] + '...'

    return render_template(
        'index.html',
        youtube_url=youtube_url, # Keeping URL in case user wants to click it
        video_title=video_title, # <--- NEW: Pass the video title to the template
        total_comments=len(comments),
        overall_sentiment=overall_sentiment,
        comment_categories=comment_categories,
        comments_data=comments_for_display
    )

if __name__ == '__main__':
    # You can set debug=True for development to auto-reload on code changes.
    # Set debug=False for production.
    app.run(debug=True)