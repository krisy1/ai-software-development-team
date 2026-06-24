# ============================================================
# Stage 1: Base — shared system deps & Python config
# ============================================================
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ============================================================
# Stage 2: Development — hot-reload, all deps + dev tools
# ============================================================
FROM base AS development

COPY requirements/base.txt requirements/dev.txt requirements/
RUN pip install --no-cache-dir -r requirements/dev.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug"]

# ============================================================
# Stage 3: Production — slim image, prod deps only, non-root user
# ============================================================
FROM base AS production

COPY requirements/base.txt requirements/prod.txt requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

COPY . .

RUN addgroup --system --gid 1001 app && \
    adduser --system --uid 1001 --gid 1001 app && \
    chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
  CMD curl --fail http://localhost:8000/health || exit 1

# Use gunicorn with uvicorn workers for production-grade process management
CMD ["gunicorn", "app.server:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "50", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--keep-alive", "5"]
