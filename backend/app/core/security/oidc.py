"""
OIDC/JWT token verification for Keycloak integration.
Provides dependency injection for authenticated endpoints.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, cast

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt  # type: ignore[import-untyped]

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
security = HTTPBearer(auto_error=True)
optional_security = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class TokenPayload:
    """
    Validated token payload with essential claims.

    Provides typed access to standard OIDC claims and custom attributes.
    """

    sub: str
    email: str | None
    preferred_username: str | None
    roles: list[str]
    bpn: str | None  # Catena-X Business Partner Number
    org: str | None
    clearance: str | None
    exp: datetime
    iat: datetime
    raw_claims: dict[str, Any]

    @property
    def is_publisher(self) -> bool:
        """Check if user has publisher role."""
        return "publisher" in self.roles or "tenant_admin" in self.roles or "admin" in self.roles

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return "admin" in self.roles


class JWKSClient:
    """
    JWKS (JSON Web Key Set) client for fetching and caching public keys.

    Implements key rotation handling by refetching JWKS on signature failures.
    """

    def __init__(self) -> None:
        self._keys: dict[str, dict[str, Any]] = {}
        self._last_fetch: datetime | None = None
        self._cache_duration_seconds = 3600  # 1 hour

    async def get_signing_key(self, kid: str) -> dict[str, Any]:
        """
        Get the signing key for a given key ID.

        Fetches JWKS if cache is stale or key is not found.
        """
        settings = get_settings()

        # Check if we need to refresh the cache
        now = datetime.now(UTC)
        should_refresh = (
            self._last_fetch is None
            or (now - self._last_fetch).total_seconds() > self._cache_duration_seconds
            or kid not in self._keys
        )

        if should_refresh:
            await self._fetch_jwks(settings.keycloak_jwks_url)

        if kid not in self._keys:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token signing key not found",
            )

        return self._keys[kid]

    async def _fetch_jwks(self, jwks_url: str) -> None:
        """Fetch and parse JWKS from the identity provider."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(jwks_url, timeout=10.0)
                response.raise_for_status()
                jwks_data = cast(dict[str, Any], response.json())

            self._keys = {}
            for key_data in jwks_data.get("keys", []):
                if (
                    isinstance(key_data, dict)
                    and key_data.get("use") == "sig"
                    and "kid" in key_data
                ):
                    kid_value = str(key_data["kid"])
                    self._keys[kid_value] = key_data

            self._last_fetch = datetime.now(UTC)
            logger.info("jwks_refreshed", key_count=len(self._keys))

        except httpx.HTTPError as e:
            logger.error("jwks_fetch_failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to fetch signing keys from identity provider",
            )


# Singleton JWKS client
_jwks_client = JWKSClient()


async def _decode_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT token.

    Validates signature, expiration, and issuer claims against Keycloak configuration.
    """
    settings = get_settings()
    try:
        # Decode header to get key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing key ID",
            )

        signing_key = await _jwks_client.get_signing_key(kid)

        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            options={
                "verify_aud": False,  # Keycloak puts client ID in azp, not aud
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": False,
            },
        )

        token_issuer = payload.get("iss")
        allowed_issuers = set(settings.keycloak_allowed_issuers_all)
        if not token_issuer or token_issuer not in allowed_issuers:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token issuer",
            )

        # Extract roles from various possible locations
        roles: list[str] = []

        # Realm roles
        if "realm_access" in payload:
            roles.extend(payload["realm_access"].get("roles", []))

        # Resource roles (client-specific)
        if "resource_access" in payload:
            client_access = payload["resource_access"].get(settings.keycloak_client_id, {})
            roles.extend(client_access.get("roles", []))

        # Flat roles claim (some configurations)
        if "roles" in payload:
            roles.extend(payload["roles"])

        return TokenPayload(
            sub=payload["sub"],
            email=payload.get("email"),
            preferred_username=payload.get("preferred_username"),
            roles=list(set(roles)),  # Deduplicate
            bpn=payload.get("bpn"),
            org=payload.get("org"),
            clearance=payload.get("clearance"),
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
            iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
            raw_claims=payload,
        )

    except JWTError as e:
        logger.warning("token_verification_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> TokenPayload:
    """
    Dependency that verifies JWT tokens and extracts claims.
    """
    return await _decode_token(credentials.credentials)


async def optional_verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(optional_security)],
) -> TokenPayload | None:
    """
    Optional auth dependency for public endpoints.
    """
    if credentials is None:
        return None
    return await _decode_token(credentials.credentials)


# Type aliases for dependency injection
CurrentUser = Annotated[TokenPayload, Depends(verify_token)]
OptionalUser = Annotated[TokenPayload | None, Depends(optional_verify_token)]


async def require_publisher(user: CurrentUser) -> TokenPayload:
    """Dependency that requires publisher or admin role."""
    if not user.is_publisher:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Publisher role required",
        )
    return user


async def require_admin(user: CurrentUser) -> TokenPayload:
    """Dependency that requires admin role."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


Publisher = Annotated[TokenPayload, Depends(require_publisher)]
Admin = Annotated[TokenPayload, Depends(require_admin)]
