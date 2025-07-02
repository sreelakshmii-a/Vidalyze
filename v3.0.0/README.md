# Vidalyze 3.0.0🎥💬

**Vidalyze** - Vidalyze 3.0.0 is aiming to be a hybrid solution, offering the best of both worlds: powerful, intelligent analysis when online, and reliable (though less accurate) functionality when offline. But still a long way to go!!

## 🚀 Features

-   🔗 **Input Any YouTube Video URL**: Supports various YouTube URL formats (standard, shorts, etc.).
-   💬 **Fetch and Analyze Comments**: Efficiently retrieves up to 500 top-level comments from YouTube videos.
-   🧠 **Advanced Sentiment Analysis**:
    * **Primary**: Utilizes the **Google Gemini API** for highly nuanced sentiment classification (Positive, Neutral, Negative, Mixed) and deep contextual understanding.
    * **Fallback**: Seamlessly switches to a **TextBlob and rule-based system** for sentiment and basic categorization if the Gemini API is unavailable or unconfigured, ensuring continuous functionality.
-   📊 **Comprehensive Audience Insights**: Generates an overall summary and actionable insights based on comment sentiment distribution and common themes, powered by Gemini.
-   📈 **Detailed Sentiment Breakdown**: Provides a percentage breakdown of positive, neutral, negative, and mixed sentiments.
-    categorizes comments by themes (e.g., Suggestions, Help, Positive, Negative).
-   👥 **Useful for**: Content creators, marketers, researchers, and anyone looking to understand audience perception quickly.

---

## 🛠 Tech Stack

-   **Frontend**: HTML, CSS, JavaScript (implied by Flask's `render_template` and `jsonify` for client-side consumption).
-   **Backend**:
    * **Python**: The core programming language.
    * **Flask**: A lightweight web framework for building the API and serving the web interface.
    * **Asynchronous Operations**: `aiohttp` for efficient, non-blocking API calls.
-   **APIs/Libraries**:
    * **YouTube Data API v3**: For fetching video metadata (like title) and comments.
    * **Google Gemini API**: For advanced AI-driven sentiment analysis, categorization, and insights generation.
    * **TextBlob**: A Python library for natural language processing, used as a robust fallback for sentiment analysis.
    * **Pandas**: For efficient data manipulation and analysis of comments.
    * **python-dotenv**: For secure management of API keys via environment variables.
    * `re`, `json`, `asyncio`: Standard Python libraries for regular expressions, JSON handling, and asynchronous programming.

---
