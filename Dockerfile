# ─────────────────────────────────────────────
# Stage 1 — dependency installation
# ─────────────────────────────────────────────
FROM python:3.11-slim AS deps

WORKDIR /app

# Install system deps needed to build some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install runtime deps + gunicorn (production WSGI server)
RUN pip install --no-cache-dir -r requirements.txt gunicorn==21.2.0


# ─────────────────────────────────────────────
# Stage 2 — production image
# ─────────────────────────────────────────────
FROM python:3.11-slim AS production

# Security: never run as root
RUN useradd --create-home --no-log-init --shell /bin/bash vidalyze

WORKDIR /home/vidalyze/app

# Bring installed packages from the deps stage (keeps image smaller)
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin/gunicorn /usr/local/bin/gunicorn

# Copy only production source files — tests, legacy versions, and
# the virtualenv are excluded by .dockerignore
COPY app.py config.py youtube.py gemini.py sentiment.py storage.py ./
COPY templates/ templates/

# Own everything as the non-root user
RUN chown -R vidalyze:vidalyze /home/vidalyze/app

USER vidalyze

EXPOSE 5000

ENV FLASK_DEBUG=false \
    LOG_LEVEL=INFO \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 2 sync workers; timeout 120 s to allow Gemini batches to complete
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
