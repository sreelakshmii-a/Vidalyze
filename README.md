# 🎥💬 Vidalyze — YouTube Comment Sentiment Analyzer

**Vidalyze** is a powerful, AI-enhanced tool that analyzes the **comment section of any YouTube video** to uncover audience sentiment and generate intelligent, actionable insights. Whether you're a content creator, marketer, or researcher, **Vidalyze helps you understand how people feel**—at scale.

---

## 🚀 Key Features

- 🔗 **Analyze Any YouTube Video**  
  Paste any YouTube link (standard or Shorts) and get started instantly.

- 💬 **Fetch and Process Comments**  
  Retrieves up to **500 top-level comments** from the selected video.

- 🧠 **Advanced Sentiment Analysis**  
  - **Primary Engine**: Uses **Google Gemini API** for **nuanced** sentiment classification: Positive, Neutral, Negative, or Mixed.  
  - **Fallback System**: Automatically switches to **TextBlob + rule-based logic** if Gemini is unavailable—ensuring **robust offline capability**.

- 📊 **Comprehensive Audience Insights**  
  - Overall sentiment percentages  
  - Smart **categorization** of comments (Suggestions, Praise, Criticism, etc.)  
  - Summarized highlights and themes (via Gemini)

- 👀 **User-Centric Insights**  
  Perfect for:
  - 📈 YouTube Creators
  - 🎯 Digital Marketers
  - 🧪 Academic Researchers
  - 🗣️ Media Analysts

---

## 🛠️ Tech Stack

| Layer      | Tools Used |
|------------|------------|
| **Frontend** | HTML, CSS, JavaScript (via Flask templates) |
| **Backend** | Python + Flask |
| **Asynchronous Ops** | `aiohttp`, `asyncio` |
| **Data Handling** | Pandas, Regex, JSON |
| **APIs & AI** | YouTube Data API v3, Google Gemini API, TextBlob |
| **Environment Management** | python-dotenv |

---

---

## 📦 Installation Guide

1.  **Clone the Repository**
    ```bash
    git clone (https://github.com/sreelakshmii-a/vidalyze.git)
    cd vidalyze
    ```
2.  **Set Up Environment Variables**
    Create a `.env` file in the root directory with your API keys:

    ```env
    YOUTUBE_API_KEY="YOUR_YOUTUBE_API_KEY"
    GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
    ```
    💡 Don’t have a Gemini API key? No problem — Vidalyze will gracefully fall back to a TextBlob-based analyzer.

3.  **Install Dependencies**

    ```bash
    pip install -r requirements.txt
    ```
4.  **Run the App**

    ```bash
    python app.py
    ```
    Open your browser and navigate to:
    👉 `http://127.0.0.1:5000`

---