"""
Redis-based sliding window rate limiting middleware.
"""

from __future__ import annotations

import time

import redis.asyncio as redis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Module-level Redis connection shared across requests
_redis: redis.Redis | None = None


async def get_redis() -> redis.Redis | None:
    """Get or create the module-level Redis connection."""
    global _redis
    if _redis is None:
        settings = get_settings()
        try:
            _redis = redis.from_url(str(settings.redis_url), decode_responses=True)  # type: ignore[no-untyped-call]
            await _redis.ping()
        except Exception:
            logger.warning("rate_limit_redis_unavailable")
            _redis = None
    return _redis


async def close_redis() -> None:
    """Close the Redis connection (call at shutdown)."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter backed by Redis.

    Applies per-IP limits to API paths only.
    Fails open if Redis is unavailable.
    """

    AUTHENTICATED_LIMIT = 200  # requests per minute
    UNAUTHENTICATED_LIMIT = 60
    WINDOW_SECONDS = 60

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()

        # Skip in development
        if settings.environment == "development":
            return await call_next(request)

        # Only rate-limit API paths
        if not request.url.path.startswith(settings.api_v1_prefix):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        has_auth = "authorization" in request.headers
        limit = self.AUTHENTICATED_LIMIT if has_auth else self.UNAUTHENTICATED_LIMIT

        r = await get_redis()
        if r is None:
            # Fail open — Redis unavailable
            return await call_next(request)

        key = f"rl:{client_ip}:{int(time.time()) // self.WINDOW_SECONDS}"

        try:
            current = await r.incr(key)
            if current == 1:
                await r.expire(key, self.WINDOW_SECONDS)
            remaining = max(0, limit - current)
        except Exception:
            logger.warning("rate_limit_redis_error", client_ip=client_ip)
            return await call_next(request)

        if current > limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={
                    "Retry-After": str(self.WINDOW_SECONDS),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
