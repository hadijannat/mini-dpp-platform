# Multi-stage Dockerfile for development and production

# =============================================================================
# Base Stage - Common dependencies
# =============================================================================
FROM python:3.12-slim as base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install system dependencies required for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, deterministic dependency management
COPY --from=ghcr.io/astral-sh/uv:0.6@sha256:4a6c9444b126bd325fba904bff796bf91fb777bf6148d60109c4cb1de2ffc497 /uv /usr/local/bin/uv

# =============================================================================
# Development Stage
# =============================================================================
FROM base as development

# Install development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files (context is repo root)
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./

# Create a shared virtual environment outside the bind-mounted /app directory.
RUN python -m venv "$VIRTUAL_ENV"

# Install dependencies using uv with locked versions into the active environment.
RUN uv sync --frozen --extra dev --extra test --active

# Copy application code
COPY backend/ .

# Copy shared registry (consumed by semantic_registry.py via parents[3] → /)
COPY shared/ /shared/

# Development server with hot reload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# =============================================================================
# Production Stage
# =============================================================================
FROM base as production

# Create non-root user for security
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Copy dependency files (context is repo root)
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./

# Create a shared virtual environment outside the bind-mounted /app directory.
RUN python -m venv "$VIRTUAL_ENV"

# Install production dependencies only using locked versions into the active environment.
RUN uv sync --frozen --active

# Copy application code
COPY --chown=appuser:appgroup backend/ .

# Copy shared registry
COPY --chown=appuser:appgroup shared/ /shared/

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

# Production server with multiple workers
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
