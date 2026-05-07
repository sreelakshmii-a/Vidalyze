import logging
import re
from collections import Counter

from textblob import TextBlob

from config import TEXTBLOB_NEGATIVE_THRESHOLD, TEXTBLOB_POSITIVE_THRESHOLD

logger = logging.getLogger(__name__)

# Keyword sets for rule-based categorization (lowercase)
_SUGGESTION_WORDS = {"suggestion", "suggest", "improve", "add", "consider", "feature", "idea", "ideas", "recommend"}
_HELP_WORDS = {"help", "trouble", "issue", "fix", "bug", "question", "how to", "problem", "error", "broken", "not working"}
_POSITIVE_WORDS = {"thank", "thanks", "awesome", "great", "love", "amazing", "best", "good", "excellent", "perfect", "brilliant", "fantastic"}
_NEGATIVE_WORDS = {"bad", "hate", "terrible", "worst", "dislike", "cringe", "awful", "horrible", "disappointing", "useless", "trash"}


def get_sentiment_textblob(text: str) -> str:
    """
    Classifies text polarity using TextBlob.

    Note: English-only. Non-English text will likely score as Neutral.
    Thresholds are defined in config.py.
    """
    if not text:
        return "Neutral"
    polarity = TextBlob(text).sentiment.polarity
    if polarity > TEXTBLOB_POSITIVE_THRESHOLD:
        return "Positive"
    if polarity < TEXTBLOB_NEGATIVE_THRESHOLD:
        return "Negative"
    return "Neutral"


def categorize_comment(comment: str) -> str:
    """
    Rule-based comment categorizer. Checks keyword sets in priority order,
    then falls back to TextBlob polarity for uncategorized comments.
    """
    lower = comment.lower()

    if any(word in lower for word in _SUGGESTION_WORDS):
        return "Suggestion"
    if any(word in lower for word in _HELP_WORDS):
        return "Help"
    if any(word in lower for word in _POSITIVE_WORDS):
        return "Positive"
    if any(word in lower for word in _NEGATIVE_WORDS):
        return "Negative"

    sentiment = get_sentiment_textblob(comment)
    if sentiment == "Positive":
        return "Positive"
    if sentiment == "Negative":
        return "Negative"
    return "Neutral/Other"


def analyze_sentiment_fallback(comments: list[str]) -> list[dict]:
    """
    Runs TextBlob + rule-based analysis on a list of comment strings.
    Returns list of {comment, sentiment, category} dicts.
    """
    logger.info("Running TextBlob fallback analysis on %d comments...", len(comments))
    results = []
    for text in comments:
        results.append({
            "comment": text,
            "sentiment": get_sentiment_textblob(text),
            "category": categorize_comment(text),
        })
    return results


def generate_insights_fallback(categorized_comments: list[dict]) -> str:
    """
    Generates a plain-text/markdown summary from fallback analysis results.
    No external API calls required.
    """
    if not categorized_comments:
        return "No comments available to generate insights."

    sentiment_counts = Counter(c["sentiment"] for c in categorized_comments)
    category_counts = Counter(c["category"] for c in categorized_comments)
    total = len(categorized_comments)

    lines = [
        "### Fallback Analysis Summary\n",
        "_This analysis used local TextBlob + rule-based categorization "
        "(Gemini API key not configured or unavailable)._\n",
        "**Sentiment Distribution:**",
    ]
    for sentiment, count in sentiment_counts.most_common():
        pct = round(count / total * 100, 2)
        lines.append(f"- {sentiment}: {pct}%")

    lines.append("\n**Top Comment Categories:**")
    for category, count in category_counts.most_common(5):
        lines.append(f"- {category}: {count} comments")

    lines.append("\n**Observations:**")
    pos_pct = sentiment_counts.get("Positive", 0) / total * 100
    neg_pct = sentiment_counts.get("Negative", 0) / total * 100

    if pos_pct > 50:
        lines.append("- Overall audience sentiment is largely positive.")
    elif neg_pct > 30:
        lines.append("- There is a notable level of negative feedback — worth reviewing.")
    else:
        lines.append("- Sentiment is mixed or predominantly neutral.")

    if category_counts.get("Suggestion", 0) > 0:
        lines.append("- Viewers are actively suggesting improvements.")
    if category_counts.get("Help", 0) > 0:
        lines.append("- Some viewers are reporting issues or seeking help.")

    lines.append("\n_For AI-powered insights, configure your GEMINI_API_KEY._")
    return "\n".join(lines)


_STOPWORDS = frozenset({
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "is","it","this","that","was","are","be","have","has","had","do","did",
    "will","would","could","should","may","might","i","you","he","she","we",
    "they","me","him","her","us","them","my","your","his","our","their","its",
    "what","which","who","when","where","how","if","not","no","so","as","by",
    "from","up","out","about","into","then","than","more","also","just","like",
    "get","got","can","been","were","am","s","t","re","ve","ll","d","im",
    "very","really","much","many","some","any","all","most","well","even",
    "video","watch","time","make","one","know","see","good","great","love",
    "comment","channel","please","think","want","need","still","back","thing",
})


def compute_word_frequencies(categorized_comments: list[dict], top_n: int = 60) -> dict:
    """
    Returns the top_n most frequent meaningful words across all comments.
    Tokenises with a simple regex, filters short words and common stopwords.
    No external dependencies required.
    """
    words: list[str] = []
    for item in categorized_comments:
        tokens = re.findall(r"[a-z]+", item.get("comment", "").lower())
        words.extend(t for t in tokens if len(t) > 3 and t not in _STOPWORDS)
    return dict(Counter(words).most_common(top_n))


def compute_sentiment_timeline(
    categorized_comments: list[dict], chunk_size: int = 20
) -> list[dict]:
    """
    Batches comments into chunks of chunk_size (oldest → newest) and returns
    the sentiment percentage breakdown per chunk.

    YouTube returns comments newest-first, so the list is reversed before
    chunking to produce a chronological timeline.
    """
    ordered = list(reversed(categorized_comments))
    chunks: list[dict] = []
    for i in range(0, len(ordered), chunk_size):
        batch = ordered[i : i + chunk_size]
        if not batch:
            continue
        counts = Counter(item.get("sentiment", "Neutral") for item in batch)
        total  = len(batch)
        chunks.append({
            "chunk":    len(chunks) + 1,
            "Positive": round(counts.get("Positive", 0) / total * 100, 1),
            "Neutral":  round(counts.get("Neutral",  0) / total * 100, 1),
            "Negative": round(counts.get("Negative", 0) / total * 100, 1),
            "Mixed":    round(counts.get("Mixed",    0) / total * 100, 1),
        })
    return chunks


def compute_stats(categorized_comments: list[dict]) -> tuple[dict, dict]:
    """
    Computes sentiment distribution (percentages) and category counts.
    Replaces the previous Pandas dependency.

    Returns:
        (overall_sentiment, comment_categories)
        e.g. ({"Positive": 62.5, "Negative": 37.5}, {"Positive": 5, "Help": 3})
    """
    if not categorized_comments:
        return {}, {}

    total = len(categorized_comments)
    sentiment_counts = Counter(c["sentiment"] for c in categorized_comments)
    category_counts = Counter(c["category"] for c in categorized_comments)

    overall_sentiment = {
        sentiment: round(count / total * 100, 2)
        for sentiment, count in sentiment_counts.most_common()
    }
    return overall_sentiment, dict(category_counts.most_common())
