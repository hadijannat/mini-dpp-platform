"""
Application configuration using Pydantic Settings.
All configuration is loaded from environment variables with sensible defaults.
"""

import json
import warnings
from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, PostgresDsn, RedisDsn, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    The configuration hierarchy allows for environment-specific overrides
    while maintaining secure defaults for production deployments.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ==========================================================================
    # Core Application Settings
    # ==========================================================================
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = Field(default=False)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # API Configuration
    api_v1_prefix: str = "/api/v1"
    project_name: str = "Mini DPP Platform"
    version: str = "0.1.0"

    # ==========================================================================
    # Database Configuration
    # ==========================================================================
    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+asyncpg://dpp_user:password@localhost:5432/dpp_platform")
    )
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=20, ge=0, le=100)
    database_pool_timeout: int = Field(default=30, ge=1)
    db_admin_role: str | None = Field(
        default="dpp_admin_bypass",
        description="Optional DB role for platform admin RLS bypass",
    )

    # ==========================================================================
    # Redis Configuration
    # ==========================================================================
    redis_url: RedisDsn = Field(default=RedisDsn("redis://localhost:6379/0"))
    redis_rate_limit_url: RedisDsn | None = Field(
        default=None,
        description="Separate Redis URL for rate limiting (defaults to DB 1 of redis_url)",
    )
    redis_cache_ttl: int = Field(default=3600, description="Cache TTL in seconds")

    # ==========================================================================
    # Keycloak / OIDC Configuration
    # ==========================================================================
    keycloak_server_url: str = Field(default="http://localhost:8080")
    keycloak_realm: str = Field(default="dpp-platform")
    keycloak_client_id: str = Field(default="dpp-backend")
    keycloak_client_secret: str = Field(default="")
    keycloak_allowed_client_ids: str | None = Field(
        default=None,
        description=(
            "Optional list of additional client IDs accepted for token validation. "
            "Supports comma-separated values or a JSON array string."
        ),
    )
    keycloak_issuer_url_override: str | None = Field(
        default=None,
        description="Override issuer URL when Keycloak is accessed via a different hostname",
    )
    keycloak_allowed_issuers: str | None = Field(
        default=None,
        description=(
            "Optional list of additional issuer URLs accepted for token validation. "
            "Supports comma-separated values or a JSON array string."
        ),
    )
    keycloak_jwks_url_override: str | None = Field(
        default=None,
        description="Override JWKS URL when Keycloak is accessed via a different hostname",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def keycloak_issuer_url(self) -> str:
        """Construct the OIDC issuer URL from Keycloak configuration."""
        if self.keycloak_issuer_url_override:
            return self.keycloak_issuer_url_override
        return f"{self.keycloak_server_url}/realms/{self.keycloak_realm}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def keycloak_allowed_issuers_all(self) -> list[str]:
        """All allowed issuer URLs, including the primary issuer."""
        issuers = [self.keycloak_issuer_url, *self._parse_allowed_issuers()]
        deduped: list[str] = []
        for issuer in issuers:
            if issuer and issuer not in deduped:
                deduped.append(issuer)
        return deduped

    @computed_field  # type: ignore[prop-decorator]
    @property
    def keycloak_allowed_client_ids_all(self) -> list[str]:
        """All allowed client IDs for azp validation."""
        clients = [self.keycloak_client_id, *self._parse_allowed_client_ids()]
        deduped: list[str] = []
        for client_id in clients:
            if client_id and client_id not in deduped:
                deduped.append(client_id)
        return deduped

    @computed_field  # type: ignore[prop-decorator]
    @property
    def keycloak_jwks_url(self) -> str:
        """Construct the JWKS endpoint URL for token verification."""
        if self.keycloak_jwks_url_override:
            return self.keycloak_jwks_url_override
        return f"{self.keycloak_issuer_url}/protocol/openid-connect/certs"

    def _parse_allowed_issuers(self) -> list[str]:
        raw = self.keycloak_allowed_issuers
        if raw is None:
            return []
        raw = raw.strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip() for item in raw.split(",") if item.strip()]

    def _parse_allowed_client_ids(self) -> list[str]:
        raw = self.keycloak_allowed_client_ids
        if raw is None:
            return []
        raw = raw.strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip() for item in raw.split(",") if item.strip()]

    # ==========================================================================
    # OPA (Open Policy Agent) Configuration
    # ==========================================================================
    opa_enabled: bool = Field(
        default=True,
        description="Enable OPA-backed ABAC enforcement",
    )
    opa_url: str = Field(default="http://localhost:8181")
    opa_policy_path: str = Field(default="v1/data/dpp/authz")
    opa_timeout: float = Field(default=1.0, description="OPA request timeout in seconds")

    # ==========================================================================
    # MinIO / Object Storage Configuration
    # ==========================================================================
    minio_endpoint: str = Field(default="localhost:9000")
    minio_access_key: str = Field(default="minio_admin")
    minio_secret_key: str = Field(default="")
    minio_secure: bool = Field(default=False)
    minio_bucket_attachments: str = Field(default="dpp-attachments")
    minio_bucket_exports: str = Field(default="dpp-exports")

    # ==========================================================================
    # Security Configuration
    # ==========================================================================
    encryption_master_key: str = Field(
        default="", description="Base64-encoded 256-bit master key for envelope encryption"
    )

    # Trusted proxy CIDRs for X-Forwarded-For / X-Real-IP header trust.
    # Only requests arriving from these CIDRs will have proxy headers honoured.
    trusted_proxy_cidrs: list[str] = Field(
        default=["172.16.0.0/12", "10.0.0.0/8", "127.0.0.0/8"],
        description="CIDRs from which X-Forwarded-For is trusted (Docker bridge, loopback)",
    )

    # CORS settings
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://dpp-frontend:5173",
        ]
    )

    # ==========================================================================
    # Template Registry Configuration
    # ==========================================================================
    idta_templates_base_url: str = Field(
        default="https://raw.githubusercontent.com/admin-shell-io/submodel-templates/main/published"
    )
    idta_templates_repo_api_url: str = Field(
        default="https://api.github.com/repos/admin-shell-io/submodel-templates/contents/published",
        description="GitHub API base URL for resolving template download locations",
    )
    idta_templates_repo_ref: str = Field(
        default="main",
        description="Git ref for the IDTA template repository (branch or tag)",
    )
    idta_templates_github_token: str | None = Field(
        default=None,
        description="Optional GitHub token to avoid API rate limits when resolving templates",
    )
    template_cache_ttl: int = Field(
        default=86400, description="Template cache TTL in seconds (default: 24 hours)"
    )

    # DPP4.0 Template versions (pinned for stability)
    template_versions: dict[str, str] = Field(
        default={
            "digital-nameplate": "3.0.1",
            "contact-information": "1.0.1",
            "technical-data": "2.0.1",
            "carbon-footprint": "1.0.1",
            "handover-documentation": "2.0.1",
            "hierarchical-structures": "1.1.1",
            # IDTA 02035 Battery Passport (7 parts)
            "battery-general-product-info": "1.0.0",
            "battery-performance-durability": "1.0.0",
            "battery-materials": "1.0.0",
            "battery-supply-chain": "1.0.0",
            "battery-end-of-life": "1.0.0",
            "battery-labels-compliance": "1.0.0",
            "battery-condition": "1.0.0",
        }
    )

    # ==========================================================================
    # DPP Integrity / JWS Signing Configuration
    # ==========================================================================
    dpp_signing_key: str = Field(
        default="",
        description=(
            "PEM-encoded private key (RSA or EC) for JWS signing of published DPP digests. "
            "If empty, published revisions will not be signed."
        ),
    )
    dpp_signing_algorithm: str = Field(
        default="RS256",
        description="JWS algorithm for DPP digest signing (RS256, ES256, etc.)",
    )
    dpp_signing_key_id: str = Field(
        default="dpp-platform-key-1",
        description="Key ID (kid) included in JWS header for key rotation support",
    )

    # ==========================================================================
    # Data Carrier / GS1 Configuration
    # ==========================================================================
    gs1_resolver_url: str = Field(
        default="https://id.gs1.org",
        description="GS1 Digital Link resolver URL for QR code generation",
    )

    # ==========================================================================
    # Identifier Configuration
    # ==========================================================================
    global_asset_id_base_uri_default: str = Field(
        default="http://localhost:8000/asset/",
        description="Default base URI for globalAssetId generation",
    )

    # ==========================================================================
    # Production Safety Checks
    # ==========================================================================

    _DEFAULT_CORS_ORIGINS = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://dpp-frontend:5173",
    ]

    @model_validator(mode="after")
    def _validate_production_settings(self) -> Self:
        """Enforce critical security settings in production/staging."""
        if self.environment in ("production", "staging"):
            if not self.encryption_master_key:
                raise ValueError(
                    f"encryption_master_key must be set in {self.environment} environment"
                )
            if self.debug:
                raise ValueError(f"debug must be False in {self.environment} environment")
            if self.cors_origins == self._DEFAULT_CORS_ORIGINS:
                raise ValueError(
                    f"cors_origins must be explicitly configured in {self.environment} environment"
                )
        else:
            if not self.encryption_master_key:
                warnings.warn(
                    "encryption_master_key is empty — encrypted fields "
                    "will not work. Set it before deploying.",
                    UserWarning,
                    stacklevel=2,
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.

    Using lru_cache ensures settings are loaded once and reused,
    avoiding repeated environment variable parsing.
    """
    return Settings()
