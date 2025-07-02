# Vidalyze 🎥💬

**Vidalyze** is a powerful and intelligent tool that analyzes the comment section of any YouTube video using advanced sentiment analysis and AI-driven insights. Just input a video URL, and Vidalyze retrieves and evaluates viewer comments to reveal overall audience sentiment—positive, neutral, or negative—and generates actionable insights.

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

## 📦 Installation

1.  **Clone the repository**:
    ```bash
    git clone [https://github.com/your-username/vidalyze.git](https://github.com/sreelakshmii-a/vidalyze.git)
    cd vidalyze
    ```

2.  **Set up your environment variables**: Create a `.env` file in the root directory and add your API keys:
    ```
    YOUTUBE_API_KEY="YOUR_YOUTUBE_API_KEY"
    GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
    ```
    *(Note: The Gemini API key is optional. If not provided, Vidalyze will use the fallback TextBlob analysis.)*

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the application**:
    ```bash
    python app.py
    ```
    (Assuming your main Flask application file is `app.py`)

    The application will typically run on `http://127.0.0.1:5000`.