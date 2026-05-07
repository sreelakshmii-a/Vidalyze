<p align="center">
  <img src="assets/banner.png" alt="Vidalyze Banner" />
</p>

# Vidalyze

YouTube comment sentiment analyzer powered by Google Gemini AI — with TextBlob fallback, interactive charts, word cloud, dark mode, per-session history, and a one-command Docker deployment.

---

## What it does

Paste any YouTube URL. Vidalyze fetches up to 500 comments, classifies each one as **Positive / Neutral / Negative / Mixed**, groups them by category (Suggestions, Help requests, etc.), and generates an AI insight summary. Each analysis session is isolated to the browser that ran it — no history leaks between users.

Results are cached for one hour and persisted in SQLite so your history survives restarts.

---

## Features

| Feature | Detail |
|---|---|
| Sentiment analysis | Gemini 2.0 Flash (primary) · TextBlob + rule-based (fallback) |
| AI highlights | Top insights · Common complaints · Feature requests (Gemini only) |
| Sentiment over time | Area line chart showing sentiment trend across comment batches |
| Word cloud | Top 50 most-used words rendered with wordcloud2.js |
| Charts | Sentiment donut + breakdown legend · Top Topics animated bar rows |
| Recent comments | Last 5 comments preview strip with sentiment dots |
| Dark mode | System-aware, toggleable, persists in `localStorage` |
| CSV export | One-click download of all analyzed comments |
| Session isolation | History scoped per browser via `X-Session-Id` — zero cross-user leakage |
| History panel | Last 20 analyses for your session, click any to re-run instantly |
| Loading screen | Page loader + 3-step progress indicator + slow-connection notice |
| Caching | 1-hour in-memory TTL cache by video ID |
| Rate limiting | 5 analysis requests per minute per IP |
| Favicon | SVG play-button icon, works in all modern browsers |

---

## Project structure

```
vidalyze/
├── app.py                    # Flask routes, caching, rate limiting, session handling
├── config.py                 # All constants and environment loading
├── youtube.py                # YouTube Data API v3 client
├── gemini.py                 # Gemini async client (sentiment + insights + highlights)
├── sentiment.py              # TextBlob fallback, stats, word frequencies, timeline
├── storage.py                # SQLite history with per-session scoping (WAL mode)
├── templates/
│   └── index.html            # Full-stack single-page UI (app-shell layout)
├── static/
│   └── favicon.svg           # SVG favicon
├── tests/                    # 125 pytest tests (all mocked, no real API calls)
│   ├── conftest.py
│   ├── test_routes.py
│   ├── test_sentiment.py
│   ├── test_session_isolation.py
│   ├── test_storage.py
│   └── test_youtube.py
├── Dockerfile                # Multi-stage production image
├── docker-compose.yml        # Compose with named volume for DB persistence
├── requirements.txt
├── pyproject.toml            # ruff + pytest + coverage config (v5.0.0)
├── Makefile                  # Developer shortcuts
└── .env.example              # Key template — copy to .env
```

---

## Quick start — local Python

### Step 1 — Prerequisites

- **Python 3.10+** (`python --version`)
- **Git**
- API keys (see Step 2)

### Step 2 — Get your API keys

**YouTube Data API v3** (required)
1. Go to [console.cloud.google.com](https://console.cloud.google.com/)
2. Create a project → Enable **YouTube Data API v3** → Create an API Key
3. Copy the key

**Google Gemini API** (optional — enables AI insights, highlights, and richer analysis)
1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click **Create API key** → Copy the key

> **No Gemini key?** Vidalyze automatically falls back to TextBlob + rule-based analysis. You still get sentiment charts, word cloud, and category breakdown — just no AI-generated narrative or highlights.

### Step 3 — Clone and set up

```bash
git clone https://github.com/sreelakshmii-a/vidalyze.git
cd vidalyze
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

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

> **Important:** Never commit `.env` — it is in `.gitignore`.

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

# 2. Start with Docker Compose (builds image + mounts DB volume automatically)
docker compose up
```

Open [http://localhost:5000](http://localhost:5000).

The SQLite database is stored in a named Docker volume (`vidalyze_data`) so analysis history **survives container restarts and image rebuilds**. To inspect or back up the database:

```bash
docker volume inspect vidalyze_vidalyze_data
```

Or run standalone (history lost on container removal):
```bash
docker build -t vidalyze:latest .
docker run --rm -p 5000:5000 --env-file .env vidalyze:latest
```

---

## Developer workflow

The `Makefile` has all common tasks:

```bash
make help          # show all commands

make run           # start Flask dev server (FLASK_DEBUG=true)
make test          # run 125-test suite
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
gcloud auth configure-docker
docker build -t gcr.io/YOUR_PROJECT/vidalyze:latest .
docker push gcr.io/YOUR_PROJECT/vidalyze:latest

gcloud run deploy vidalyze \
  --image gcr.io/YOUR_PROJECT/vidalyze:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars YOUTUBE_API_KEY=xxx,GEMINI_API_KEY=xxx
```

> Use **Google Secret Manager** instead of `--set-env-vars` for production keys.
>
> Note: Cloud Run containers are stateless. For persistent history, set `DB_DIR` to a Cloud Storage FUSE mount or switch to Cloud SQL.

### Option B — Railway (fastest, 5 minutes)

1. Push your repo to GitHub
2. Go to [railway.app](https://railway.app/) → New Project → Deploy from GitHub repo
3. Set environment variables in the Railway dashboard (Settings → Variables)
4. Railway auto-detects the Dockerfile and deploys

Add a Railway Volume mounted at `/home/vidalyze/data` and set `DB_DIR=/home/vidalyze/data` to persist history.

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
| `DB_DIR` | No | App directory | Directory for `vidalyze.db` — set to a mounted volume path in production |

---

## YouTube API quota

The YouTube Data API v3 has a **10,000 unit daily quota** per project.

| Operation | Cost |
|---|---|
| Fetch video metadata | 1 unit |
| Fetch 100 comments | 1 unit |
| Fetch 500 comments (max) | 5 units |

A typical full analysis costs ~6 units — roughly **1,600 analyses per day** on the free quota.

Vidalyze's 1-hour in-memory cache means the same video only costs quota **once per hour** regardless of how many users view it.

---

## Running the tests

```bash
# All 125 tests (no real API calls — everything is mocked)
pytest tests/ -v

# With coverage
pytest tests/ --cov=. --cov-report=term-missing
```

Tests are organised by module:

| File | What it covers |
|---|---|
| `test_youtube.py` | URL extraction (14 cases) · comment fetch · error paths |
| `test_sentiment.py` | TextBlob thresholds · categorizer · fallback pipeline · word frequencies · timeline |
| `test_routes.py` | Flask routes · validation · cache · error handlers |
| `test_storage.py` | SQLite init · save · history ordering · JSON decoding |
| `test_session_isolation.py` | Per-session history scoping · DB migration · header validation · route isolation |

---

## Troubleshooting

**`YOUTUBE_API_KEY is not set`**
→ Make sure `.env` exists in the project root. Verify: `python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('YOUTUBE_API_KEY'))"`.

**`Comments are disabled for this video`**
→ The creator has disabled comments. Try a different video.

**`YouTube API Quota Exceeded`**
→ You've used your 10,000 daily units. Wait until midnight Pacific time, or create a second Google Cloud project with a new key.

**Analysis is slow (30+ seconds)**
→ Gemini processes all 500 comments in one request. Normal for the first analysis. Re-running the same video is instant (served from cache).

**History shows different results on another device**
→ By design — history is scoped to each browser via an anonymous session ID stored in `localStorage`. Each browser has its own independent history.

**`ModuleNotFoundError`**
→ Virtual environment is not activated, or `pip install -r requirements.txt` was not run.

**Docker: `exec /usr/local/bin/gunicorn: no such file or directory`**
→ Run `docker build --target production -t vidalyze .` and check for errors in the deps stage.

**Docker: history lost after restart**
→ Use `docker compose up` (not `docker run`) — Compose mounts the `vidalyze_data` named volume automatically.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 · Flask 3.0 · Flask-Limiter |
| Async HTTP | aiohttp · asyncio |
| AI / NLP | Google Gemini 2.0 Flash · TextBlob |
| APIs | YouTube Data API v3 |
| Caching | cachetools TTLCache |
| Storage | SQLite3 (stdlib) — WAL mode, per-session scoping |
| Frontend | Tailwind CSS · Chart.js 4 · wordcloud2.js · marked.js · DOMPurify · Geist font |
| Testing | pytest · pytest-cov (125 tests) |
| Linting | ruff |
| Container | Docker (multi-stage) · gunicorn · named volume for persistence |
| CI/CD | GitHub Actions (test matrix · lint · secret scan · Docker build) |

---

## License

MIT — free to use, modify, and distribute with attribution.
