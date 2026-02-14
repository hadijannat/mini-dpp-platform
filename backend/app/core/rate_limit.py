"""
Redis-based sliding window rate limiting middleware.
"""

from __future__ import annotations

import inspect
import ipaddress
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


def _get_rate_limit_redis_url() -> str:
    """Return the Redis URL for rate limiting (separate DB to avoid LRU eviction)."""
    settings = get_settings()
    if settings.redis_rate_limit_url:
        return str(settings.redis_rate_limit_url)
    # Default: use DB 1 of the same Redis instance (cache uses DB 0)
    base = str(settings.redis_url)
    if base.endswith("/0"):
        return base[:-1] + "1"
    return base


async def get_redis() -> redis.Redis | None:
    """Get or create the module-level Redis connection for rate limiting."""
    global _redis
    if _redis is None:
        try:
            url = _get_rate_limit_redis_url()
            _redis = redis.from_url(url, decode_responses=True)  # type: ignore[no-untyped-call]
            ping_result = _redis.ping()
            if inspect.isawaitable(ping_result):
                await ping_result
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


def _is_trusted_proxy(remote_ip: str) -> bool:
    """Check whether *remote_ip* falls within a configured trusted proxy CIDR."""
    settings = get_settings()
    try:
        addr = ipaddress.ip_address(remote_ip)
    except ValueError:
        return False
    return any(
        addr in ipaddress.ip_network(cidr, strict=False) for cidr in settings.trusted_proxy_cidrs
    )


def get_client_ip(request: Request) -> str:
    """Extract real client IP, only trusting proxy headers from known proxies.

    If the direct connection comes from a trusted proxy CIDR, the
    X-Forwarded-For / X-Real-IP headers are honoured.  Otherwise the
    connection's remote address is returned directly, preventing IP spoofing.
    """
    connection_ip = request.client.host if request.client else "unknown"

    if connection_ip == "unknown" or not _is_trusted_proxy(connection_ip):
        return connection_ip

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # X-Forwarded-For: client, proxy1, proxy2 — leftmost is the real client
        client_ip = forwarded_for.split(",")[0].strip()
        if client_ip:
            return client_ip

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    return connection_ip


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter backed by Redis.

    Applies per-IP limits to API paths only.
    Fails open if Redis is unavailable — rate limiting is defense-in-depth,
    not the sole authentication/authorization mechanism.
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

        client_ip = get_client_ip(request)
        # Auth presence check determines rate tier only — actual authentication
        # is enforced by the OIDC dependency in route handlers.
        has_auth = "authorization" in request.headers
        limit = self.AUTHENTICATED_LIMIT if has_auth else self.UNAUTHENTICATED_LIMIT

        r = await get_redis()
        if r is None:
            # Fail open — Redis unavailable
            return await call_next(request)

        key = f"rl:{client_ip}:{int(time.time()) // self.WINDOW_SECONDS}"

        try:
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, self.WINDOW_SECONDS)
            results: list[int | bool] = await pipe.execute()
            current = int(results[0])
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


def _get_client_ip(request: Request) -> str:
    """Backwards-compatible alias for older imports/tests."""
    return get_client_ip(request)
