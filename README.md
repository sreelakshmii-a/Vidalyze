# Vidalyze

YouTube comment sentiment analyzer powered by Google Gemini AI — with TextBlob fallback, charts, dark mode, history, and a one-command Docker deployment.

---

## What it does

Paste any YouTube URL. Vidalyze fetches up to 500 comments, classifies each one as **Positive / Neutral / Negative / Mixed**, groups them by category (Suggestions, Help, etc.), generates an AI insight summary, and — when Gemini is configured — extracts the top comments, complaints, and feature requests as highlighted callout cards.

Results are cached for one hour and saved to a local SQLite database so you can browse your history between sessions.

---

## Features

| Feature | Detail |
|---|---|
| Sentiment analysis | Gemini 2.0 Flash (primary) · TextBlob + rule-based (fallback) |
| AI highlights | Top insights · Common complaints · Feature requests (Gemini only) |
| Charts | Sentiment donut · Category horizontal bar (Chart.js) |
| Dark mode | System-aware, toggleable, persists in localStorage |
| CSV export | One-click download of all analyzed comments |
| History panel | Last 20 analyses, click any to re-run instantly |
| Caching | 1-hour in-memory TTL cache by video ID |
| Rate limiting | 5 analysis requests per minute per IP |
| Accessibility | Screen-reader labels, sentiment icons, aria attributes |

---

## Project structure

```
vidalyze/
├── app.py            # Flask routes + caching + rate limiting
├── config.py         # All constants and environment loading
├── youtube.py        # YouTube Data API v3 client
├── gemini.py         # Gemini async client + highlights
├── sentiment.py      # TextBlob fallback + stats
├── storage.py        # SQLite history (auto-created as vidalyze.db)
├── templates/
│   └── index.html    # Full-stack single-page UI
├── tests/            # 94 pytest tests (all mocked, no real API calls)
├── Dockerfile        # Multi-stage production image
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml    # ruff + pytest + coverage config
├── Makefile          # Developer shortcuts
├── .env.example      # Key template — copy to .env
└── AUDIT.md          # Living issue registry
```

---

## Quick start — local Python

### Step 1 — Prerequisites

- **Python 3.10+** (`python --version`)
- **Git**
- API keys (see Step 2)

### Step 2 — Get your API keys

You need a **YouTube Data API v3** key. The **Gemini API** key is optional but unlocks the best analysis.

**YouTube Data API v3** (required)
1. Go to [console.cloud.google.com](https://console.cloud.google.com/)
2. Create a project (or select an existing one)
3. Enable the **YouTube Data API v3**: APIs & Services → Library → search "YouTube Data API v3" → Enable
4. Create credentials: APIs & Services → Credentials → Create Credentials → API Key
5. Copy the key

**Google Gemini API** (optional — enables AI insights and highlights)
1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click **Create API key**
3. Copy the key

> **No Gemini key?** Vidalyze automatically falls back to TextBlob + rule-based analysis. You still get sentiment charts and categories — just no AI-generated narrative or highlights.

### Step 3 — Clone and set up

```bash
git clone https://github.com/YOUR_USERNAME/vidalyze.git
cd vidalyze
```

Create a virtual environment:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### Step 4 — Configure API keys

```bash
cp .env.example .env
```

Open `.env` and fill in your keys:
```env
YOUTUBE_API_KEY=AIzaSy...your_key_here
GEMINI_API_KEY=AIzaSy...your_key_here   # optional
FLASK_DEBUG=false
LOG_LEVEL=INFO
```

> **Important:** Never commit `.env` — it is in `.gitignore`. Your keys stay local.

### Step 5 — Run

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## Quick start — Docker (recommended for sharing / deployment)

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

### One-command run

```bash
# 1. Copy and fill in your keys
cp .env.example .env
# (edit .env with your API keys)

# 2. Build the image
docker build -t vidalyze:latest .

# 3. Run
docker run --rm -p 5000:5000 --env-file .env vidalyze:latest
```

Or with Docker Compose (even simpler):
```bash
docker compose up
```

Open [http://localhost:5000](http://localhost:5000).

---

## Developer workflow

The `Makefile` has all common tasks:

```bash
make help          # show all commands

make run           # start Flask dev server (FLASK_DEBUG=true)
make test          # run 94-test suite
make test-cov      # tests + coverage report
make lint          # ruff check
make lint-fix      # ruff auto-fix

make docker-build  # build production image
make docker-run    # run container (requires .env)
make docker-down   # stop container

make clean         # remove __pycache__, .pytest_cache, coverage files
```

---

## Deploying to the cloud

### Option A — GCP Cloud Run (recommended)

Cloud Run makes sense since you're already using Google APIs (YouTube + Gemini). Free tier covers light usage.

```bash
# Build and push to Google Container Registry
gcloud auth configure-docker
docker build -t gcr.io/YOUR_PROJECT/vidalyze:latest .
docker push gcr.io/YOUR_PROJECT/vidalyze:latest

# Deploy
gcloud run deploy vidalyze \
  --image gcr.io/YOUR_PROJECT/vidalyze:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars YOUTUBE_API_KEY=xxx,GEMINI_API_KEY=xxx
```

Use **Google Secret Manager** instead of `--set-env-vars` for production keys.

### Option B — Railway (fastest, 5 minutes)

1. Push your repo to GitHub
2. Go to [railway.app](https://railway.app/) → New Project → Deploy from GitHub repo
3. Set environment variables in the Railway dashboard (Settings → Variables)
4. Railway auto-detects the Dockerfile and deploys

### Option C — Render

1. Push to GitHub
2. New Web Service on [render.com](https://render.com/) → connect repo
3. Set Environment Variables in the Render dashboard
4. Render auto-builds and deploys on every push

---

## Environment variables reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `YOUTUBE_API_KEY` | Yes | — | YouTube Data API v3 key |
| `GEMINI_API_KEY` | No | — | Gemini API key (enables AI analysis) |
| `FLASK_DEBUG` | No | `false` | Set `true` only for local dev |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` · `INFO` · `WARNING` · `ERROR` |

---

## YouTube API quota

The YouTube Data API v3 has a **10,000 unit daily quota** per project.

| Operation | Cost |
|---|---|
| Fetch video metadata | 1 unit |
| Fetch 100 comments | 1 unit |
| Fetch 500 comments (max) | 5 units |

A typical full analysis costs ~6 units. At 10,000 units/day that's roughly **1,600 full analyses per day** on the free quota — plenty for personal or small-team use.

Vidalyze's 1-hour in-memory cache means the same video only costs quota **once per hour** regardless of how many users view it.

---

## Running the tests

```bash
# All 94 tests (no real API calls — everything is mocked)
pytest tests/ -v

# With coverage
pytest tests/ --cov=. --cov-report=term-missing
```

Tests are organised by module:

| File | What it covers |
|---|---|
| `tests/test_youtube.py` | URL extraction (14 cases) · comment fetch · error paths |
| `tests/test_sentiment.py` | TextBlob thresholds · categorizer · fallback pipeline · stats |
| `tests/test_routes.py` | Flask routes · validation · cache · error handlers |
| `tests/test_storage.py` | SQLite init · save · history ordering · JSON decoding |

---

## Troubleshooting

**`YOUTUBE_API_KEY is not set`**
→ Make sure `.env` exists in the project root and contains `YOUTUBE_API_KEY=...`. Run `python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('YOUTUBE_API_KEY'))"` to verify it loads.

**`Comments are disabled for this video`**
→ The video creator has turned off comments. Try a different video.

**`YouTube API Quota Exceeded`**
→ You've used your 10,000 daily units. Wait until midnight Pacific time (quota resets). Or create a second Google Cloud project with a new API key.

**Analysis is slow (30+ seconds)**
→ Gemini is processing 500 comments in batches. Normal for the first run. Second run for the same video is instant (served from cache).

**`ModuleNotFoundError`**
→ Your virtual environment is not activated, or `pip install -r requirements.txt` was not run. Activate the venv and reinstall.

**Docker: `exec /usr/local/bin/gunicorn: no such file or directory`**
→ The multi-stage build must complete both stages. Run `docker build --target production -t vidalyze .` and check for errors in the deps stage.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 · Flask 3.0 · Flask-Limiter |
| Async HTTP | aiohttp · asyncio |
| AI / NLP | Google Gemini 2.0 Flash · TextBlob |
| APIs | YouTube Data API v3 |
| Caching | cachetools TTLCache |
| Storage | SQLite3 (stdlib) |
| Frontend | Tailwind CSS · Chart.js 4 · marked.js · DOMPurify |
| Testing | pytest · pytest-cov (94 tests) |
| Linting | ruff |
| Container | Docker (multi-stage) · gunicorn |
| CI/CD | GitHub Actions (test matrix + lint + secrets scan + Docker build) |

---

## License

MIT — free to use, modify, and distribute with attribution.
