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
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# =============================================================================
# Development Stage
# =============================================================================
FROM base as development

# Install development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock README.md ./

# Create a shared virtual environment outside the bind-mounted /app directory.
RUN python -m venv "$VIRTUAL_ENV"

# Install dependencies using uv with locked versions into the active environment.
RUN uv sync --frozen --extra dev --extra test --active

# Copy application code
COPY . .

# Development server with hot reload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# =============================================================================
# Production Stage
# =============================================================================
FROM base as production

# Create non-root user for security
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Copy dependency files
COPY pyproject.toml uv.lock README.md ./

# Create a shared virtual environment outside the bind-mounted /app directory.
RUN python -m venv "$VIRTUAL_ENV"

# Install production dependencies only using locked versions into the active environment.
RUN uv sync --frozen --active

# Copy application code
COPY --chown=appuser:appgroup . .

USER appuser

# Production server with multiple workers
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
