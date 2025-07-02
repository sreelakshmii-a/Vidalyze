# 🎥💬 Vidalyze — YouTube Comment Sentiment Analyzer

**Vidalyze** is a powerful, AI-enhanced tool that analyzes the **comment section of any YouTube video** to uncover audience sentiment and generate intelligent, actionable insights. Whether you're a content creator, marketer, or researcher, **Vidalyze helps you understand how people feel**—at scale.

---

## 🚀 Key Features

- 🔗 **Analyze Any YouTube Video**  
  Paste any YouTube link (standard or Shorts) and get started instantly.

- 💬 **Fetch and Process Comments**  
  Retrieves **top-level comments** from the selected video.

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

## 🧠 How It Works (Behind the Scenes)

1. 🎥 Accepts a YouTube video URL from the user.
2. 🔍 Validates and extracts the video ID.
3. 💬 Fetches **top-level comments** using the **YouTube Data API**.
4. 🧠 Analyzes the comments via:
   - ✅ **Google Gemini API** (if the API key is configured)
   - 🔁 **TextBlob fallback** (if Gemini is unavailable)
5. 📊 Classifies sentiments into **Positive**, **Neutral**, **Negative**, and **Mixed**.
6. 🗂️ Groups comments by themes and generates an **AI-powered summary**.
7. 🌐 Presents everything via a clean, responsive **Flask frontend**.

---

## ✅ To-Do / Future Improvements

- [ ] 📈 Add charts/visualizations for sentiment graphs  
- [ ] 📤 Option to export reports (PDF/CSV)  
- [ ] 💬 Include replies (not just top-level comments)  
- [ ] 🎯 Improve accuracy of fallback sentiment categorization  
- [ ] 🧠 Add caching to avoid redundant API calls  

---

## 🙌 Contributing

Contributions are always welcome! You can:

- 🐞 **Report issues**
- 💡 **Suggest new features**
- 🛠️ **Submit pull requests**
- 🌱 **Fork and adapt** for your own use

Feel free to open a **GitHub Discussion** or **Issue** if you have questions, feature ideas, or improvements to suggest.

---

## 🔐 License

This project is licensed under the **MIT License**.

> ✅ You're free to **use**, **modify**, and **distribute** this project — just provide proper attribution.

---

## 💬 Let's Connect

Have questions, feedback, or cool ideas?  
Open an issue or discussion on GitHub — and don’t forget to ⭐ the repo if it helped you!

---

## 💡 Want More?

Would you like help with:

- 📛 **Badges** (e.g., GitHub stars, forks, license, Python version)?
- 🎞️ **GIF previews** or walkthrough videos of the tool in action?
- 🌐 **Live deployment setup** via:
  - [Render](https://render.com)
  - [Railway](https://railway.app)
  - [Replit](https://replit.com)

Let me know — happy to assist!
