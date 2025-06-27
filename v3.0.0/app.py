import os
import re
import json
import asyncio
import aiohttp
import pandas as pd
from flask import Flask, render_template, request, jsonify
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
from textblob import TextBlob # For fallback sentiment analysis

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# IMPORTANT: Retrieve API keys from environment variables.
# Ensure YOUTUBE_API_KEY and GEMINI_API_KEY are set in your .env file
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

app = Flask(__name__)

# --- YouTube Data API Functions ---

def get_video_id(youtube_url):
    """
    Extracts the YouTube video ID from a given URL.
    Supports various YouTube URL formats.
    """
    if not youtube_url:
        print("Error: YouTube URL cannot be empty.")
        return None

    # Regex patterns for common YouTube URL formats
    patterns = [
        r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=|embed\/|v\/|)([\w-]{11})(?:\S+)?",
        r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/shorts\/([\w-]{11})(?:\S+)?"
    ]

    for pattern in patterns:
        match = re.search(pattern, youtube_url)
        if match:
            return match.group(1)
    print(f"Error: Could not extract video ID from URL: {youtube_url}")
    return None

def fetch_youtube_comments(video_id, youtube_api_key, max_results=500):
    """
    Fetches comments for a given YouTube video ID using the YouTube Data API v3.
    Note: This API only returns top-level comments or a subset of replies depending on settings.
    """
    if not video_id:
        return [], "Error: Video ID is missing."
    if not youtube_api_key:
        return [], "Error: YouTube API Key is not set. Please ensure YOUTUBE_API_KEY is in your .env file or environment variables."

    try:
        youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=youtube_api_key)
    except Exception as e:
        return [], f"Error initializing YouTube service: {e}"

    comments = []
    next_page_token = None
    fetched_count = 0

    print(f"Fetching comments for video ID: {video_id}...")

    try:
        while fetched_count < max_results:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                textFormat="plainText",
                maxResults=min(max_results - fetched_count, 100),  # Max 100 per request
                pageToken=next_page_token
            )
            response = request.execute()

            for item in response['items']:
                comment_text = item['snippet']['topLevelComment']['snippet']['textDisplay']
                comments.append(comment_text)
                fetched_count += 1
                if fetched_count >= max_results:
                    break

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break # No more pages

            print(f"Fetched {len(comments)} comments so far. Fetching next page...")

    except HttpError as e:
        error_details = e.error_details[0] if e.error_details else {}
        reason = error_details.get('reason')
        message = error_details.get('message')
        print(f"YouTube API Error: {e}")

        if e.resp.status == 403:
            if reason == 'commentsDisabled':
                return [], "Comments are disabled for this video by the creator."
            elif reason == 'quotaExceeded' or 'dailyLimitExceeded' in str(message):
                return [], "YouTube API Quota Exceeded. Please try again later or check your Google Cloud project settings."
            else:
                return [], f"Access Denied (403): {message or 'Unknown reason.'}"
        elif e.resp.status == 404:
            return [], "Video not found. Please check the video URL."
        else:
            return [], f"An unexpected YouTube API error occurred (Status {e.resp.status}): {message or 'No specific message.'}"
    except Exception as e:
        print(f"An unexpected error occurred while fetching comments: {e}")
        return [], f"An unexpected error occurred: {e}"

    print(f"Successfully fetched {len(comments)} comments.")
    return comments, None

# --- Gemini API Functions ---

async def call_gemini_api(prompt, api_key, schema=None):
    """
    Makes an asynchronous call to the Gemini API with a given prompt and optional schema.
    """
    if not api_key:
        print("Error: Gemini API Key is not set. Cannot call Gemini API.")
        return None

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}]
    }

    if schema:
        payload["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseSchema": schema
        }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, headers=headers, data=json.dumps(payload)) as response:
                response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
                result = await response.json()

                if result.get('candidates') and result['candidates'][0].get('content') and result['candidates'][0]['content'].get('parts'):
                    if schema:
                        json_str = result['candidates'][0]['content']['parts'][0]['text']
                        try:
                            parsed_json = json.loads(json_str)
                            return parsed_json
                        except json.JSONDecodeError:
                            print(f"Error: Gemini returned invalid JSON: {json_str}")
                            return None
                    else:
                        return result['candidates'][0]['content']['parts'][0]['text']
                else:
                    print(f"Gemini API response structure unexpected: {result}")
                    return None
    except aiohttp.ClientError as e:
        print(f"Network or Client error calling Gemini API: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during Gemini API call: {e}")
        return None

async def analyze_sentiment_and_categorize_gemini(comments, gemini_api_key):
    """
    Analyzes the sentiment of each comment and categorizes it using Gemini.
    Returns a list of dictionaries with comment and its categorized sentiment.
    """
    categorized_comments = []
    if not comments:
        print("No comments to analyze with Gemini.")
        return []
    if not gemini_api_key:
        print("Gemini API key not provided, skipping Gemini analysis.")
        return []

    print(f"Analyzing sentiment for {len(comments)} comments using Gemini...")

    sentiment_schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "comment": {"type": "STRING", "description": "The original comment text."},
                "sentiment": {"type": "STRING", "enum": ["Positive", "Neutral", "Negative", "Mixed"], "description": "The sentiment of the comment."}
            },
            "required": ["comment", "sentiment"]
        }
    }

    # Split comments into batches to avoid hitting API request limits or context window limits
    batch_size = 100 # Adjusted for potentially longer comments and API limits
    for i in range(0, len(comments), batch_size):
        batch = comments[i:i + batch_size]
        # Ensure comments are properly escaped for JSON or simply passed as a list of strings
        # For this prompt, using a simple list of strings for the model to process is fine.
        batch_prompt = "Analyze the sentiment of the following YouTube comments. For each comment, classify its sentiment as 'Positive', 'Neutral', 'Negative', or 'Mixed'. Provide the output as a JSON array of objects, where each object has 'comment' (the original comment text) and 'sentiment' fields.\n\nComments:\n" + "\n".join([f"- {c}" for c in batch])

        print(f"Processing batch {i // batch_size + 1} of Gemini analysis...")
        response_data = await call_gemini_api(batch_prompt, gemini_api_key, sentiment_schema)

        if response_data:
            if isinstance(response_data, dict) and "sentiment" in response_data and "comment" in response_data:
                response_data = [response_data] # Handle single object response as a list
            elif not isinstance(response_data, list):
                print(f"Warning: Unexpected Gemini response format for sentiment analysis: {response_data}. Skipping batch.")
                continue

            for item in response_data:
                sentiment = item.get('sentiment')
                if sentiment not in ["Positive", "Neutral", "Negative", "Mixed"]:
                    sentiment = "Neutral" # Default to Neutral if sentiment is unidentifiable

                categorized_comments.append({
                    "comment": item.get('comment', 'N/A'),
                    "sentiment": sentiment,
                    "category": sentiment # For Gemini, sentiment is also the primary category
                })
        else:
            print(f"Failed to get sentiment analysis for batch starting with comment: {batch[0] if batch else 'N/A'}")

    return categorized_comments

async def generate_overall_insights_gemini(categorized_comments, gemini_api_key):
    """
    Generates an overall summary and insights based on the categorized comments using Gemini.
    """
    if not categorized_comments:
        return "No comments available to generate insights."
    if not gemini_api_key:
        print("Gemini API key not provided, skipping Gemini insights generation.")
        return "Overall insights could not be generated using Gemini (API key missing)."

    print("Generating overall insights and summary using Gemini...")

    sentiment_groups = {
        "Positive": [], "Neutral": [], "Negative": [], "Mixed": []
    }
    for item in categorized_comments:
        sentiment_groups[item['sentiment']].append(item['comment'])

    # Limit comments for prompt to avoid exceeding context window
    positive_comments_formatted = '- ' + '\n- '.join(sentiment_groups['Positive'][:5])
    neutral_comments_formatted = '- ' + '\n- '.join(sentiment_groups['Neutral'][:5])
    negative_comments_formatted = '- ' + '\n- '.join(sentiment_groups['Negative'][:5])
    mixed_comments_formatted = '- ' + '\n- '.join(sentiment_groups['Mixed'][:5])


    insight_prompt = f"""
Based on the following categorized YouTube comments, provide an overall summary of the audience sentiment and key insights.
Consider the distribution of positive, neutral, negative, and mixed comments. Highlight common themes or recurring feedback within each sentiment category.
Focus on providing actionable insights that creators, marketers, or researchers could use.

Here's a breakdown of the top 5 comments by sentiment (if available):

Positive Comments ({len(sentiment_groups['Positive'])} comments):
{positive_comments_formatted if sentiment_groups['Positive'] else 'No positive comments.'}

Neutral Comments ({len(sentiment_groups['Neutral'])} comments):
{neutral_comments_formatted if sentiment_groups['Neutral'] else 'No neutral comments.'}

Negative Comments ({len(sentiment_groups['Negative'])} comments):
{negative_comments_formatted if sentiment_groups['Negative'] else 'No negative comments.'}

Mixed Comments ({len(sentiment_groups['Mixed'])} comments):
{mixed_comments_formatted if sentiment_groups['Mixed'] else 'No mixed comments.'}

Overall Sentiment Distribution:
Positive: {len(sentiment_groups['Positive'])}
Neutral: {len(sentiment_groups['Neutral'])}
Negative: {len(sentiment_groups['Negative'])}
Mixed: {len(sentiment_groups['Mixed'])}

Provide a concise summary and actionable insights in Markdown format.
"""
    insights = await call_gemini_api(insight_prompt, gemini_api_key)
    return insights if insights else "Could not generate overall insights using Gemini."

# --- Fallback (TextBlob) Functions ---

def get_sentiment_textblob(text):
    """
    Analyzes the sentiment of the given text using TextBlob.
    Returns 'Positive', 'Negative', or 'Neutral'.
    """
    analysis = TextBlob(text)
    if analysis.sentiment.polarity > 0.1:
        return "Positive"
    elif analysis.sentiment.polarity < -0.1:
        return "Negative"
    else:
        return "Neutral"

def categorize_comment_rule_based(comment):
    """
    Categorizes a comment based on keywords.
    This is a basic rule-based approach.
    """
    comment_lower = comment.lower()

    if any(word in comment_lower for word in ["suggestion", "suggest", "improve", "add", "consider", "feature", "ideas"]):
        return "Suggestion"
    elif any(word in comment_lower for word in ["help", "trouble", "issue", "fix", "bug", "question", "how to", "problem"]):
        return "Help"
    elif any(word in comment_lower for word in ["thank", "awesome", "great", "love", "amazing", "best", "good"]):
        return "Positive"
    elif any(word in comment_lower for word in ["bad", "hate", "terrible", "worst", "dislike", "cringe"]):
        return "Negative"
    else:
        sentiment = get_sentiment_textblob(comment)
        if sentiment == "Positive":
            return "Positive"
        elif sentiment == "Negative":
            return "Negative"
        else:
            return "Neutral/Other"

def generate_overall_insights_fallback(categorized_comments):
    """
    Generates a simple overall summary and insights based on TextBlob/rule-based categories.
    """
    if not categorized_comments:
        return "No comments available to generate fallback insights."

    sentiment_counts = pd.DataFrame(categorized_comments)['sentiment'].value_counts(normalize=True) * 100
    category_counts = pd.DataFrame(categorized_comments)['category'].value_counts()

    summary = "### Fallback Analysis Summary\n\n"
    summary += "This analysis was performed using a local TextBlob model and rule-based categorization.\n\n"
    summary += "**Overall Sentiment Distribution:**\n"
    for sentiment, percentage in sentiment_counts.items():
        summary += f"- {sentiment}: {percentage:.2f}%\n"

    summary += "\n**Top Comment Categories:**\n"
    if not category_counts.empty:
        for category, count in category_counts.head(5).items():
            summary += f"- {category}: {count} comments\n"
    else:
        summary += "No specific categories identified.\n"

    summary += "\n**General Observations:**\n"
    if "Positive" in sentiment_counts.index and sentiment_counts["Positive"] > 50:
        summary += "- The overall sentiment appears to be largely positive.\n"
    elif "Negative" in sentiment_counts.index and sentiment_counts["Negative"] > 30:
        summary += "- There is a notable amount of negative feedback.\n"
    else:
        summary += "- Sentiment is mixed or predominantly neutral.\n"

    if "Suggestion" in category_counts.index and category_counts["Suggestion"] > 0:
        summary += "- Users are actively providing suggestions for improvement.\n"
    if "Help" in category_counts.index and category_counts["Help"] > 0:
        summary += "- Some users are seeking help or reporting issues.\n"

    summary += "\n*For more detailed and nuanced insights, consider setting up your Gemini API key.*"
    return summary

# --- Flask Routes ---

@app.route('/', methods=['GET'])
def index():
    """Renders the main page with the input form."""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
async def analyze():
    """
    Handles the analysis request, fetches comments, performs sentiment analysis
    (Gemini or fallback), and returns results as JSON.
    """
    youtube_url = request.form['youtube_url']
    video_id = get_video_id(youtube_url)

    if not video_id:
        return jsonify({"error": "Invalid YouTube URL provided. Please check the format."}), 400

    # Initialize YouTube service
    youtube_service = None
    try:
        youtube_service = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=YOUTUBE_API_KEY)
    except Exception as e:
        return jsonify({"error": f"Failed to initialize YouTube API service: {e}. Please check your YOUTUBE_API_KEY."}), 500

    # Fetch video title
    video_title = "Video Title Not Found" # Default title in case of error
    try:
        video_request = youtube_service.videos().list(part="snippet", id=video_id)
        video_response = video_request.execute()
        if video_response and 'items' in video_response and len(video_response['items']) > 0:
            video_title = video_response['items'][0]['snippet']['title']
        else:
            video_title = "Video Details Unavailable"
    except HttpError as e:
        print(f"Error fetching video title: {e}")
        video_title = f"Error fetching title (Status {e.resp.status})"
    except Exception as e:
        print(f"An unexpected error occurred while fetching video title: {e}")
        video_title = "Error fetching title"

    # Fetch comments
    comments, fetch_error = fetch_youtube_comments(video_id, YOUTUBE_API_KEY)

    if fetch_error:
        return jsonify({"error": fetch_error, "video_title": video_title}), 400

    if not comments:
        return jsonify({"error": "No comments found for this video or comments are disabled.", "video_title": video_title}), 400

    categorized_comments = []
    overall_insights = ""
    analysis_method = "TextBlob/Rule-Based Fallback" # Default to fallback

    # Attempt Gemini analysis first
    if GEMINI_API_KEY:
        try:
            print("Attempting Gemini analysis...")
            gemini_categorized = await analyze_sentiment_and_categorize_gemini(comments, GEMINI_API_KEY)
            if gemini_categorized:
                categorized_comments = gemini_categorized
                overall_insights = await generate_overall_insights_gemini(categorized_comments, GEMINI_API_KEY)
                analysis_method = "Gemini"
                print("Gemini analysis successful.")
            else:
                print("Gemini analysis returned no results or failed, falling back to TextBlob.")
        except Exception as e:
            print(f"Gemini analysis failed: {e}. Falling back to TextBlob.")
    else:
        print("GEMINI_API_KEY not set. Using TextBlob/Rule-Based Fallback.")

    # If Gemini failed or not configured, use fallback
    if analysis_method != "Gemini":
        print("Performing TextBlob/rule-based fallback analysis.")
        for comment_text in comments:
            sentiment = get_sentiment_textblob(comment_text)
            category = categorize_comment_rule_based(comment_text)
            categorized_comments.append({
                "comment": comment_text,
                "sentiment": sentiment,
                "category": category
            })
        overall_insights = generate_overall_insights_fallback(categorized_comments)

    # Prepare data for frontend
    total_comments = len(comments)
    df = pd.DataFrame(categorized_comments)

    overall_sentiment = (df["sentiment"].value_counts(normalize=True) * 100).round(2).to_dict()
    comment_categories = df["category"].value_counts().to_dict()

    comments_for_display = df.to_dict(orient='records')

    return jsonify({
        "youtube_url": youtube_url,
        "video_title": video_title,
        "total_comments": total_comments,
        "overall_sentiment": overall_sentiment,
        "comment_categories": comment_categories,
        "comments_data": comments_for_display,
        "overall_insights": overall_insights,
        "analysis_method": analysis_method
    })

if __name__ == '__main__':
    app.run(debug=True)
