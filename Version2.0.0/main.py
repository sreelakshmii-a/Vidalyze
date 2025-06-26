import os
import re
from googleapiclient.discovery import build
import json
import asyncio
import aiohttp
from dotenv import load_dotenv # Import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# IMPORTANT: Retrieve API keys from environment variables.
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

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

def fetch_youtube_comments(video_id, youtube_api_key):
    """
    Fetches comments for a given YouTube video ID using the YouTube Data API v3.
    Note: This API only returns top-level comments or a subset of replies depending on settings.
    """
    if not video_id:
        print("Error: Video ID is missing.")
        return []
    if not youtube_api_key: # Check if key is None after loading
        print("Error: YouTube API Key is not set. Please ensure YOUTUBE_API_KEY is in your .env file or environment variables.")
        return []

    youtube = build('youtube', 'v3', developerKey=youtube_api_key)
    comments = []
    next_page_token = None

    print(f"Fetching comments for video ID: {video_id}...")

    try:
        while True:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                textFormat="plainText",
                maxResults=100,  # Max results per page
                pageToken=next_page_token
            )
            response = request.execute()

            for item in response['items']:
                comment_text = item['snippet']['topLevelComment']['snippet']['textDisplay']
                comments.append(comment_text)

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
            print(f"Fetched {len(comments)} comments so far. Fetching next page...")

    except Exception as e:
        print(f"An error occurred while fetching comments: {e}")
        # Specific error handling for API quotas or invalid keys
        if "quotaExceeded" in str(e):
            print("YouTube API Quota Exceeded. Please try again later or check your Google Cloud project settings.")
        elif "developerKeyInvalid" in str(e) or "keyInvalid" in str(e):
            print("Invalid YouTube API Key. Please ensure your key is correct and enabled for YouTube Data API v3.")
        return []

    print(f"Successfully fetched {len(comments)} comments.")
    return comments

# --- Gemini API Functions ---

async def call_gemini_api(prompt, api_key, schema=None):
    """
    Makes an asynchronous call to the Gemini API with a given prompt and optional schema.
    """
    if not api_key: # Check if key is None after loading
        print("Error: Gemini API Key is not set. Please ensure GEMINI_API_KEY is in your .env file or environment variables.")
        return None

    # Base URL for Gemini API
    # Using gemini-2.0-flash as requested
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
        headers['Content-Type'] = 'application/json' # Ensure Content-Type is set for structured responses

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, headers=headers, data=json.dumps(payload)) as response:
                response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
                result = await response.json()

                if result.get('candidates') and result['candidates'][0].get('content') and result['candidates'][0]['content'].get('parts'):
                    if schema:
                        # For structured responses, parse the text part as JSON
                        json_str = result['candidates'][0]['content']['parts'][0]['text']
                        try:
                            parsed_json = json.loads(json_str)
                            return parsed_json
                        except json.JSONDecodeError:
                            print(f"Error: Gemini returned invalid JSON: {json_str}")
                            return None
                    else:
                        # For plain text responses
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

async def analyze_sentiment_and_categorize(comments, gemini_api_key):
    """
    Analyzes the sentiment of each comment and categorizes it using Gemini.
    Returns a list of dictionaries with comment and its categorized sentiment.
    """
    categorized_comments = []
    if not comments:
        print("No comments to analyze.")
        return []

    print(f"Analyzing sentiment for {len(comments)} comments using Gemini...")

    # Define the JSON schema for the sentiment analysis response
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
    # and to provide intermediate feedback.
    batch_size = 50 # Adjust batch size based on API limits and comment length
    for i in range(0, len(comments), batch_size):
        batch = comments[i:i + batch_size]
        batch_prompt = "Analyze the sentiment of the following YouTube comments. For each comment, classify its sentiment as 'Positive', 'Neutral', 'Negative', or 'Mixed'. Provide the output as a JSON array of objects, where each object has 'comment' (the original comment text) and 'sentiment' fields.\n\nComments:\n" + "\n".join([f"- {c}" for c in batch])

        print(f"Processing batch {i // batch_size + 1}...")
        response_data = await call_gemini_api(batch_prompt, gemini_api_key, sentiment_schema)

        if response_data:
            # Ensure the response is a list, even if Gemini sometimes wraps a single item
            if isinstance(response_data, dict) and "sentiment" in response_data and "comment" in response_data:
                response_data = [response_data] # Handle single object response as a list
            elif not isinstance(response_data, list):
                print(f"Warning: Unexpected Gemini response format for sentiment analysis: {response_data}. Skipping batch.")
                continue

            for item in response_data:
                # Add a fallback for sentiment if not explicitly provided or invalid
                sentiment = item.get('sentiment')
                if sentiment not in ["Positive", "Neutral", "Negative", "Mixed"]:
                    sentiment = "Neutral" # Default to Neutral if sentiment is unidentifiable

                categorized_comments.append({
                    "comment": item.get('comment', 'N/A'),
                    "sentiment": sentiment
                })
        else:
            print(f"Failed to get sentiment analysis for batch starting with comment: {batch[0] if batch else 'N/A'}")

    return categorized_comments

async def generate_overall_insights(categorized_comments, gemini_api_key):
    """
    Generates an overall summary and insights based on the categorized comments.
    """
    if not categorized_comments:
        return "No comments available to generate insights."

    print("Generating overall insights and summary...")

    # Group comments by sentiment for better summary generation
    sentiment_groups = {
        "Positive": [],
        "Neutral": [],
        "Negative": [],
        "Mixed": []
    }
    for item in categorized_comments:
        sentiment_groups[item['sentiment']].append(item['comment'])

    # Pre-format comment lists to avoid backslashes in f-string expressions
    positive_comments_formatted = '- ' + '\n- '.join(sentiment_groups['Positive'][:10])
    if len(sentiment_groups['Positive']) > 10:
        positive_comments_formatted += '\n...'

    neutral_comments_formatted = '- ' + '\n- '.join(sentiment_groups['Neutral'][:10])
    if len(sentiment_groups['Neutral']) > 10:
        neutral_comments_formatted += '\n...'

    negative_comments_formatted = '- ' + '\n- '.join(sentiment_groups['Negative'][:10])
    if len(sentiment_groups['Negative']) > 10:
        negative_comments_formatted += '\n...'

    mixed_comments_formatted = '- ' + '\n- '.join(sentiment_groups['Mixed'][:10])
    if len(sentiment_groups['Mixed']) > 10:
        mixed_comments_formatted += '\n...'


    # Create a prompt for overall insights
    insight_prompt = f"""
Based on the following categorized YouTube comments, provide an overall summary of the audience sentiment and key insights.
Consider the distribution of positive, neutral, negative, and mixed comments. Highlight common themes or recurring feedback within each sentiment category.
Focus on providing actionable insights that creators, marketers, or researchers could use.

Here's a breakdown of the comments by sentiment:

Positive Comments ({len(sentiment_groups['Positive'])} comments):
{positive_comments_formatted}

Neutral Comments ({len(sentiment_groups['Neutral'])} comments):
{neutral_comments_formatted}

Negative Comments ({len(sentiment_groups['Negative'])} comments):
{negative_comments_formatted}

Mixed Comments ({len(sentiment_groups['Mixed'])} comments):
{mixed_comments_formatted}

Overall Sentiment Distribution:
Positive: {len(sentiment_groups['Positive'])}
Neutral: {len(sentiment_groups['Neutral'])}
Negative: {len(sentiment_groups['Negative'])}
Mixed: {len(sentiment_groups['Mixed'])}

Provide a concise summary and actionable insights in Markdown format.
"""
    insights = await call_gemini_api(insight_prompt, gemini_api_key)
    return insights

# --- Display Functions ---

def display_results(categorized_comments, insights):
    """
    Displays the categorized comments and the overall insights.
    """
    print("\n--- Vidalyze Analysis Results ---")
    print("\nOverall Audience Sentiment and Insights:")
    print(insights if insights else "Could not generate overall insights.")

    print("\n--- Categorized Comments ---")
    if not categorized_comments:
        print("No comments were fetched or analyzed.")
        return

    # Group and sort for better display
    sentiment_order = ["Positive", "Neutral", "Negative", "Mixed"]
    grouped_for_display = {sentiment: [] for sentiment in sentiment_order}

    for item in categorized_comments:
        sentiment = item.get("sentiment", "Unknown")
        comment = item.get("comment", "N/A")
        if sentiment in grouped_for_display:
            grouped_for_display[sentiment].append(comment)
        else:
            print(f"Warning: Unknown sentiment '{sentiment}' encountered for comment: '{comment}'")

    for sentiment in sentiment_order:
        comments_list = grouped_for_display[sentiment]
        if comments_list:
            print(f"\n## {sentiment} Comments ({len(comments_list)}):")
            for i, comment in enumerate(comments_list):
                print(f"{i+1}. {comment}")
        else:
            print(f"\n## {sentiment} Comments (0):")
            print("No comments in this category.")

# --- Main Execution Flow ---

async def main_vidalyze_flow(youtube_url):
    """
    Main function to orchestrate the Vidalyze process.
    """
    print(f"Starting Vidalyze analysis for URL: {youtube_url}")

    # 1. Get video ID
    video_id = get_video_id(youtube_url)
    if not video_id:
        print("Exiting: Invalid YouTube URL provided.")
        return

    # 2. Fetch comments
    comments = fetch_youtube_comments(video_id, YOUTUBE_API_KEY)
    if not comments:
        print("Exiting: No comments fetched or an error occurred during fetching.")
        return

    # 3. Analyze sentiment and categorize with Gemini
    categorized_comments = await analyze_sentiment_and_categorize(comments, GEMINI_API_KEY)
    if not categorized_comments:
        print("Exiting: Sentiment analysis failed or returned no results.")
        return

    # 4. Generate overall insights with Gemini
    overall_insights = await generate_overall_insights(categorized_comments, GEMINI_API_KEY)

    # 5. Display results
    display_results(categorized_comments, overall_insights)

# --- Example Usage ---
if __name__ == "__main__":
    # IMPORTANT: Replace with a YouTube video URL you want to analyze.
    # Ensure the video has comments.
    example_youtube_url = "https://youtu.be/Kk2bDwRVxb8?si=MYURGRIG6FjkDL0O" # Rick Astley - Never Gonna Give You Up
    # Or test with a short video with fewer comments for quicker testing
    # example_youtube_url = "https://www.youtube.com/watch?v=some_short_video_id"

    # Run the main asynchronous flow
    asyncio.run(main_vidalyze_flow(example_youtube_url))
