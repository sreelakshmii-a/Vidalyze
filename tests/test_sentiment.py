"""
Tests for sentiment.py — TextBlob classification, rule-based categorization,
fallback analysis pipeline, and stats computation.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sentiment import (
    analyze_sentiment_fallback,
    categorize_comment,
    compute_stats,
    generate_insights_fallback,
    get_sentiment_textblob,
)

# ---------------------------------------------------------------------------
# get_sentiment_textblob
# ---------------------------------------------------------------------------

class TestGetSentimentTextblob:
    def test_clearly_positive(self):
        assert get_sentiment_textblob("This is absolutely amazing and wonderful!") == "Positive"

    def test_clearly_negative(self):
        assert get_sentiment_textblob("This is terrible, awful, and completely horrible.") == "Negative"

    def test_neutral_factual(self):
        assert get_sentiment_textblob("The video was uploaded on Tuesday at 3pm.") == "Neutral"

    def test_empty_string_returns_neutral(self):
        assert get_sentiment_textblob("") == "Neutral"

    def test_returns_valid_label(self):
        result = get_sentiment_textblob("Some random comment with no clear feeling")
        assert result in ("Positive", "Neutral", "Negative")

    def test_strong_positive_words(self):
        assert get_sentiment_textblob("Great work! Excellent tutorial, very good content.") == "Positive"

    def test_strong_negative_words(self):
        assert get_sentiment_textblob("Worst video ever, completely useless and bad.") == "Negative"


# ---------------------------------------------------------------------------
# categorize_comment
# ---------------------------------------------------------------------------

class TestCategorizeComment:
    def test_suggestion_keyword(self):
        assert categorize_comment("I suggest you add more examples to improve this video") == "Suggestion"

    def test_improve_keyword(self):
        assert categorize_comment("You should improve the audio quality") == "Suggestion"

    def test_feature_keyword(self):
        assert categorize_comment("Can you consider adding a feature for dark mode?") == "Suggestion"

    def test_help_keyword(self):
        assert categorize_comment("I need help, I have a problem with this code") == "Help"

    def test_bug_keyword(self):
        assert categorize_comment("There is a bug in the script, how do I fix it?") == "Help"

    def test_positive_keyword_thank(self):
        assert categorize_comment("Thank you so much for this tutorial!") == "Positive"

    def test_positive_keyword_awesome(self):
        assert categorize_comment("This is awesome content, keep it up!") == "Positive"

    def test_negative_keyword_hate(self):
        assert categorize_comment("I hate this so much, it is the worst.") == "Negative"

    def test_negative_keyword_terrible(self):
        assert categorize_comment("Terrible quality, very disappointing") == "Negative"

    def test_priority_suggestion_over_positive(self):
        # "suggest" should win over "great" due to keyword priority order
        result = categorize_comment("Great video! I suggest you add more examples.")
        assert result == "Suggestion"

    def test_fallback_to_textblob_neutral(self):
        # No keywords → falls through to TextBlob
        result = categorize_comment("The video was uploaded today at noon.")
        assert result in ("Neutral/Other", "Positive", "Negative")

    def test_case_insensitive(self):
        assert categorize_comment("HELP ME FIX THIS ISSUE PLEASE") == "Help"


# ---------------------------------------------------------------------------
# analyze_sentiment_fallback
# ---------------------------------------------------------------------------

class TestAnalyzeSentimentFallback:
    def test_returns_correct_length(self, sample_comments):
        result = analyze_sentiment_fallback(sample_comments)
        assert len(result) == len(sample_comments)

    def test_result_has_required_keys(self, sample_comments):
        result = analyze_sentiment_fallback(sample_comments)
        for item in result:
            assert "comment" in item
            assert "sentiment" in item
            assert "category" in item

    def test_sentiment_values_valid(self, sample_comments):
        valid = {"Positive", "Neutral", "Negative"}
        result = analyze_sentiment_fallback(sample_comments)
        for item in result:
            assert item["sentiment"] in valid

    def test_category_values_valid(self, sample_comments):
        valid = {"Positive", "Negative", "Neutral/Other", "Suggestion", "Help"}
        result = analyze_sentiment_fallback(sample_comments)
        for item in result:
            assert item["category"] in valid

    def test_empty_list_returns_empty(self):
        assert analyze_sentiment_fallback([]) == []

    def test_comment_text_preserved(self, sample_comments):
        result = analyze_sentiment_fallback(sample_comments)
        returned_texts = [r["comment"] for r in result]
        assert returned_texts == sample_comments


# ---------------------------------------------------------------------------
# generate_insights_fallback
# ---------------------------------------------------------------------------

class TestGenerateInsightsFallback:
    def test_returns_string(self, sample_categorized):
        result = generate_insights_fallback(sample_categorized)
        assert isinstance(result, str)
        assert len(result) > 50

    def test_empty_input(self):
        result = generate_insights_fallback([])
        assert "No comments" in result

    def test_contains_sentiment_info(self, sample_categorized):
        result = generate_insights_fallback(sample_categorized)
        assert any(word in result for word in ("Positive", "Negative", "Neutral"))

    def test_markdown_format(self, sample_categorized):
        result = generate_insights_fallback(sample_categorized)
        assert "###" in result or "**" in result

    def test_all_negative_dominant(self):
        comments = [{"comment": f"c{i}", "sentiment": "Negative", "category": "Negative"} for i in range(10)]
        result = generate_insights_fallback(comments)
        assert "negative" in result.lower()


# ---------------------------------------------------------------------------
# compute_stats
# ---------------------------------------------------------------------------

class TestComputeStats:
    def test_percentages_sum_to_100(self, sample_categorized):
        sentiment_stats, _ = compute_stats(sample_categorized)
        total = sum(sentiment_stats.values())
        assert abs(total - 100.0) < 0.1  # floating point tolerance

    def test_category_counts_sum_to_total(self, sample_categorized):
        _, category_stats = compute_stats(sample_categorized)
        assert sum(category_stats.values()) == len(sample_categorized)

    def test_empty_input(self):
        sentiment_stats, category_stats = compute_stats([])
        assert sentiment_stats == {}
        assert category_stats == {}

    def test_single_sentiment(self):
        comments = [{"comment": "A", "sentiment": "Positive", "category": "Positive"} for _ in range(4)]
        sentiment_stats, category_stats = compute_stats(comments)
        assert sentiment_stats == {"Positive": 100.0}
        assert category_stats == {"Positive": 4}

    def test_even_split(self):
        comments = (
            [{"comment": "A", "sentiment": "Positive",  "category": "Positive"}  for _ in range(2)] +
            [{"comment": "B", "sentiment": "Negative",  "category": "Negative"}  for _ in range(2)]
        )
        sentiment_stats, _ = compute_stats(comments)
        assert sentiment_stats["Positive"] == 50.0
        assert sentiment_stats["Negative"] == 50.0

    def test_rounding_to_2_decimals(self):
        comments = [{"comment": "X", "sentiment": "Positive", "category": "Positive"} for _ in range(3)]
        comments.append({"comment": "Y", "sentiment": "Negative", "category": "Negative"})
        sentiment_stats, _ = compute_stats(comments)
        for val in sentiment_stats.values():
            assert val == round(val, 2)

    def test_output_is_dict(self, sample_categorized):
        s, c = compute_stats(sample_categorized)
        assert isinstance(s, dict)
        assert isinstance(c, dict)
