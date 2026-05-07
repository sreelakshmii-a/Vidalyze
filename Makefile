# ============================================================
# Vidalyze — developer shortcuts
# Usage: make <target>
# ============================================================

.PHONY: help run test test-cov lint lint-fix docker-build docker-run docker-down clean

# Default: show help
help:
	@echo ""
	@echo "  Vidalyze — available make targets"
	@echo "  ──────────────────────────────────"
	@echo "  run          Start Flask dev server (FLASK_DEBUG=true)"
	@echo "  test         Run test suite"
	@echo "  test-cov     Run tests + coverage report"
	@echo "  lint         Check code style with ruff"
	@echo "  lint-fix     Auto-fix ruff issues"
	@echo "  docker-build Build production Docker image"
	@echo "  docker-run   Run container (requires .env file)"
	@echo "  docker-down  Stop and remove container"
	@echo "  clean        Remove build/cache artifacts"
	@echo ""

# ── Local development ────────────────────────────────────────
run:
	FLASK_DEBUG=true LOG_LEVEL=DEBUG python app.py

# ── Testing ──────────────────────────────────────────────────
test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ \
	  --cov=. \
	  --cov-report=term-missing \
	  --cov-omit="tests/*,v1.0.0/*,v2.0.0/*,v3.0.0/*,VID/*"

# ── Linting ──────────────────────────────────────────────────
lint:
	ruff check .

lint-fix:
	ruff check . --fix

# ── Docker ───────────────────────────────────────────────────
docker-build:
	docker build --target production -t vidalyze:latest .

docker-run:
	docker run --rm \
	  --name vidalyze \
	  -p 5000:5000 \
	  --env-file .env \
	  vidalyze:latest

docker-down:
	docker stop vidalyze 2>/dev/null || true

# ── Cleanup ───────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov coverage.xml .coverage
	@echo "Clean done."
