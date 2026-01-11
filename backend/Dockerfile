# Multi-stage Dockerfile for development and production

# =============================================================================
# Base Stage - Common dependencies
# =============================================================================
FROM python:3.12-slim as base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

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

# Install dependencies using uv with locked versions
RUN uv sync --frozen --extra dev --extra test

# Copy application code
COPY . .

# Development server with hot reload
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# =============================================================================
# Production Stage
# =============================================================================
FROM base as production

# Create non-root user for security
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Copy dependency files
COPY pyproject.toml uv.lock README.md ./

# Install production dependencies only using locked versions
RUN uv sync --frozen

# Copy application code
COPY --chown=appuser:appgroup . .

USER appuser

# Production server with multiple workers
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
