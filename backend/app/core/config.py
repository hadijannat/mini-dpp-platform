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
    auto_provision_default_tenant: bool = Field(
        default=True,
        description="Auto-provision users into the default tenant (dev convenience, disable in production)",
    )
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
    # CIRPASS Lab Public Feed
    # ==========================================================================
    cirpass_results_url: str = Field(
        default="https://cirpassproject.eu/project-results/",
        description="Official CIRPASS project results page used to discover latest user stories",
    )
    cirpass_refresh_ttl_seconds: int = Field(
        default=43_200,
        ge=60,
        description="Staleness threshold for CIRPASS story snapshots in seconds",
    )
    cirpass_session_ttl_seconds: int = Field(
        default=86_400,
        ge=300,
        description="TTL for public CIRPASS leaderboard session tokens in seconds",
    )
    cirpass_session_token_secret: str = Field(
        default="dev-cirpass-session-secret-change-me",
        description="HMAC secret used for signing public CIRPASS session tokens",
    )
    cirpass_leaderboard_limit_default: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Default number of rows returned for CIRPASS leaderboard endpoint",
    )
    cirpass_leaderboard_limit_max: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Hard maximum rows returned for CIRPASS leaderboard endpoint",
    )
    cirpass_lab_scenario_engine_enabled: bool = Field(
        default=True,
        description="Feature flag for data-driven CIRPASS lab scenario engine",
    )
    cirpass_lab_live_mode_enabled: bool = Field(
        default=False,
        description="Feature flag for CIRPASS lab live mode against backend APIs",
    )
    cirpass_lab_inspector_enabled: bool = Field(
        default=True,
        description="Feature flag for under-the-hood inspector panels in CIRPASS lab",
    )
    cirpass_lab_telemetry_retention_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Retention window for anonymized CIRPASS lab telemetry rows",
    )

    # ==========================================================================
    # Public Regulatory Timeline
    # ==========================================================================
    regulatory_timeline_refresh_ttl_seconds: int = Field(
        default=82_800,
        ge=300,
        description="Staleness threshold for regulatory timeline snapshots in seconds",
    )
    regulatory_timeline_cache_control_fresh: str = Field(
        default="public, max-age=300, stale-while-revalidate=3600",
        description="Cache-Control header for fresh regulatory timeline responses",
    )
    regulatory_timeline_cache_control_stale: str = Field(
        default="public, max-age=60, stale-while-revalidate=3600",
        description="Cache-Control header for stale regulatory timeline responses",
    )
    regulatory_timeline_source_timeout_seconds: int = Field(
        default=15,
        ge=3,
        le=60,
        description="HTTP timeout used when fetching official timeline sources",
    )
    regulatory_timeline_verify_max_age_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Maximum age in days for timeline verification freshness badge",
    )
    regulatory_timeline_seed_path: str | None = Field(
        default=None,
        description=(
            "Optional absolute/relative path override for regulatory timeline seed file. "
            "When unset, service falls back to repo docs seed and packaged module seed."
        ),
    )

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
    attachments_max_upload_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1024,
        description="Maximum attachment upload size in bytes",
    )
    aasx_max_upload_bytes: int = Field(
        default=50 * 1024 * 1024,
        ge=1024,
        description="Maximum AASX upload size in bytes",
    )
    mime_validation_regex: str = Field(
        default=(
            r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}/"
            r"[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}$"
        ),
        description="Open MIME policy regex used for validating content types",
    )

    # ==========================================================================
    # Security Configuration
    # ==========================================================================
    encryption_master_key: str = Field(
        default="", description="Base64-encoded 256-bit master key for envelope encryption"
    )

    metrics_auth_token: str = Field(
        default="",
        description="Bearer token for /metrics endpoint. Empty = unauthenticated in dev, 404 in production.",
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

    template_version_resolution_policy: Literal["latest_patch"] = Field(
        default="latest_patch",
        description=(
            "Template version resolution strategy. latest_patch resolves the highest "
            "available patch within configured major.minor baseline."
        ),
    )
    template_major_minor_baselines: dict[str, str] = Field(
        default={
            "carbon-footprint": "1.0",
            "contact-information": "1.0",
            "digital-nameplate": "3.0",
            "handover-documentation": "2.0",
            "hierarchical-structures": "1.1",
            "technical-data": "2.0",
        },
        description="Configured major.minor baseline per supported DPP4.0 template.",
    )
    # Legacy pinned versions retained for backward compatibility.
    template_versions: dict[str, str] = Field(
        default={
            "digital-nameplate": "3.0.1",
            "contact-information": "1.0.1",
            "technical-data": "2.0.1",
            "carbon-footprint": "1.0.1",
            "handover-documentation": "2.0.1",
            "hierarchical-structures": "1.1.1",
        },
        description="Deprecated: prefer template_major_minor_baselines + resolution policy.",
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
    dpp_max_draft_revisions: int = Field(
        default=10,
        description="Maximum number of draft revisions to keep per DPP. Published revisions are always kept.",
    )
    dpp_required_specific_asset_ids_default: list[str] = Field(
        default=["manufacturerPartId"],
        description=(
            "Default required specificAssetIds for DPP create/import validation. "
            "Can be overridden per request profile."
        ),
    )
    dpp_required_specific_asset_ids_by_template: dict[str, list[str]] = Field(
        default={},
        description=(
            "Optional per-template required specificAssetIds merged with defaults "
            "for profile-aware validation."
        ),
    )

    # ==========================================================================
    # Eclipse Dataspace Connector (EDC)
    # ==========================================================================
    edc_management_url: str = Field(default="", description="EDC Management API URL")
    edc_management_api_key: str = Field(default="", description="EDC Management API key")
    edc_dsp_endpoint: str = Field(default="", description="EDC DSP protocol endpoint")
    edc_participant_id: str = Field(default="", description="EDC participant BPN")
    dataspace_legacy_connector_write_enabled: bool = Field(
        default=True,
        description="Allow write operations on legacy /connectors create/publish endpoints",
    )
    dataspace_tck_command: str = Field(
        default="",
        description=(
            "Optional shell command used to run DSP-TCK conformance jobs. "
            "If empty, runs are recorded in simulation mode."
        ),
    )
    dataspace_tck_timeout_seconds: int = Field(
        default=900,
        ge=30,
        le=7200,
        description="Timeout for DSP-TCK command execution",
    )
    dataspace_tck_artifact_dir: str = Field(
        default="artifacts/dataspace-tck",
        description="Filesystem directory for conformance run artifacts",
    )

    # ==========================================================================
    # Audit Cryptographic Integrity
    # ==========================================================================
    audit_signing_key: str = Field(
        default="", description="PEM Ed25519 private key for audit signing"
    )
    audit_signing_public_key: str = Field(default="", description="PEM Ed25519 public key")
    tsa_url: str = Field(default="", description="RFC 3161 TSA endpoint URL")
    audit_merkle_batch_size: int = Field(default=100, description="Events per Merkle batch")

    # ==========================================================================
    # ESPR Compliance Engine
    # ==========================================================================
    compliance_check_on_publish: bool = Field(
        default=False, description="Run compliance check before publish"
    )

    # ==========================================================================
    # Digital Thread
    # ==========================================================================
    digital_thread_enabled: bool = Field(
        default=False, description="Enable digital thread event recording"
    )
    digital_thread_auto_record: bool = Field(
        default=True, description="Auto-record thread events on DPP lifecycle changes"
    )

    # ==========================================================================
    # LCA / PCF Calculation
    # ==========================================================================
    lca_enabled: bool = Field(default=False, description="Enable LCA/PCF calculation service")
    lca_default_scope: str = Field(
        default="cradle-to-gate", description="Default LCA scope boundary"
    )
    lca_scope_multipliers: dict[str, float] = Field(
        default={
            "cradle-to-gate": 1.0,
            "gate-to-gate": 0.3,
            "cradle-to-grave": 1.2,
        },
        description=(
            "Scope multipliers applied by the PCF engine. "
            "Keys must match supported LCAScope values."
        ),
    )
    lca_methodology: str = Field(
        default="activity-based-gwp",
        description="Configured methodology identifier persisted in LCA reports",
    )
    lca_methodology_disclosure: str = Field(
        default=(
            "Calculated estimate for interoperability and comparison; "
            "not a certification substitute."
        ),
        description="Disclosure text attached to LCA reports for claim governance",
    )
    lca_factor_database_path: str = Field(
        default="", description="Custom emission factors YAML path (empty = built-in)"
    )
    lca_external_pcf_enabled: bool = Field(
        default=False,
        description="Allow controlled retrieval of PCF values from ExternalPcfApi references",
    )
    lca_external_pcf_allowlist: list[str] = Field(
        default=[],
        description="Allowlisted hostnames for ExternalPcfApi calls",
    )
    lca_external_pcf_timeout_seconds: int = Field(
        default=8,
        ge=1,
        le=60,
        description="HTTP timeout for ExternalPcfApi calls",
    )
    lca_external_pcf_max_concurrency: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent outbound ExternalPcfApi requests per calculation",
    )

    # ==========================================================================
    # EPCIS 2.0
    # ==========================================================================
    epcis_enabled: bool = Field(default=False, description="Enable EPCIS 2.0 event recording")
    epcis_auto_record: bool = Field(
        default=True, description="Auto-record EPCIS events on DPP lifecycle changes"
    )
    epcis_validate_gs1_schema: bool = Field(
        default=False, description="Validate captured events against GS1 structural rules"
    )

    # ==========================================================================
    # Webhooks
    # ==========================================================================
    webhook_enabled: bool = Field(default=False, description="Enable webhook notifications")
    webhook_timeout_seconds: int = Field(
        default=10, description="HTTP timeout for webhook delivery"
    )
    webhook_max_retries: int = Field(default=3, description="Max delivery retry attempts per event")
    webhook_max_subscriptions: int = Field(
        default=25, description="Max webhook subscriptions per tenant"
    )

    # ==========================================================================
    # Email Notifications
    # ==========================================================================
    notifications_email_enabled: bool = Field(
        default=False, description="Enable SMTP email notifications for onboarding workflows"
    )
    notifications_smtp_host: str = Field(
        default="", description="SMTP relay hostname for notification emails"
    )
    notifications_smtp_port: int = Field(default=587, ge=1, le=65535)
    notifications_smtp_user: str | None = Field(
        default=None, description="Optional SMTP username for notification emails"
    )
    notifications_smtp_password: str | None = Field(
        default=None, description="Optional SMTP password for notification emails"
    )
    notifications_smtp_starttls: bool = Field(
        default=True, description="Use STARTTLS for SMTP notification transport"
    )
    notifications_from_email: str = Field(
        default="", description="From email address for notification messages"
    )
    notifications_from_name: str = Field(
        default="DPP Platform", description="From display name for notification messages"
    )
    notifications_admin_fallback_emails: str | None = Field(
        default=None,
        description=(
            "Fallback recipients for admin notifications when tenant admin emails cannot be resolved. "
            "Supports comma-separated values or a JSON array string."
        ),
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def notifications_admin_fallback_emails_all(self) -> list[str]:
        """Parsed fallback admin email recipients."""
        raw = self.notifications_admin_fallback_emails
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
    # GS1 Digital Link Resolver
    # ==========================================================================
    resolver_enabled: bool = Field(default=False, description="Enable GS1 Digital Link resolver")
    resolver_base_url: str = Field(
        default="",
        description="Base URL for resolver links (e.g., https://dpp-platform.dev/api/v1/resolve)",
    )
    resolver_auto_register: bool = Field(
        default=True,
        description="Auto-register resolver links on DPP publish",
    )

    # ==========================================================================
    # Verifiable Credentials / DID
    # ==========================================================================
    vc_enabled: bool = Field(
        default=False, description="Enable Verifiable Credentials / DID support"
    )
    vc_credential_ttl_days: int = Field(
        default=365,
        ge=1,
        le=3650,
        description="Default credential validity period in days",
    )

    # ==========================================================================
    # AAS Registry & Discovery
    # ==========================================================================
    registry_enabled: bool = Field(default=False, description="Enable built-in AAS registry")
    registry_auto_register: bool = Field(
        default=True, description="Auto-register shell descriptors on DPP publish"
    )
    registry_external_url: str = Field(
        default="", description="External BaSyx V2 registry URL (empty = use built-in)"
    )
    registry_external_discovery_url: str = Field(
        default="", description="External BaSyx V2 discovery URL"
    )

    # ==========================================================================
    # User Onboarding
    # ==========================================================================
    onboarding_auto_join_tenant_slug: str | None = Field(
        default="default",
        description="Tenant slug to auto-join on first login (None to disable)",
    )
    onboarding_require_email_verified: bool = Field(
        default=True,
        description="Require email_verified=True in JWT for auto-provisioning",
    )
    onboarding_verification_resend_cooldown_seconds: int = Field(
        default=30,
        ge=5,
        le=3600,
        description="Cooldown window in seconds between verification email resend attempts",
    )
    onboarding_verification_redirect_uri: str | None = Field(
        default=None,
        description=(
            "Optional redirect URI passed to Keycloak execute-actions-email for VERIFY_EMAIL. "
            "If unset, backend falls back to first configured CORS origin + /welcome."
        ),
    )
    onboarding_verification_client_id: str = Field(
        default="dpp-frontend",
        description="Keycloak client_id used for verification email action links",
    )

    # ==========================================================================
    # Data Carrier / GS1 Configuration
    # ==========================================================================
    gs1_resolver_url: str = Field(
        default="https://id.gs1.org",
        description="GS1 Digital Link resolver URL for QR code generation",
    )
    carrier_resolver_allowed_hosts: str | None = Field(
        default=None,
        description=(
            "Optional allowlist for resolver redirect hosts managed by data carriers. "
            "Supports comma-separated values or a JSON array string."
        ),
    )
    data_carrier_publish_gate_enabled_default: bool = Field(
        default=False,
        description=(
            "Default feature flag for requiring compliant managed data carriers before publish. "
            "Can be overridden via admin settings."
        ),
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def carrier_resolver_allowed_hosts_all(self) -> list[str]:
        """Parsed hostname allowlist for managed resolver targets."""
        raw = self.carrier_resolver_allowed_hosts
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
            if not self.dpp_signing_key:
                raise ValueError(f"dpp_signing_key must be set in {self.environment} environment")
            if self.debug:
                raise ValueError(f"debug must be False in {self.environment} environment")
            if self.cors_origins == self._DEFAULT_CORS_ORIGINS:
                raise ValueError(
                    f"cors_origins must be explicitly configured in {self.environment} environment"
                )
            if not self.opa_enabled:
                raise ValueError(f"opa_enabled must be True in {self.environment} environment")
            if self.auto_provision_default_tenant:
                raise ValueError(
                    f"auto_provision_default_tenant must be False in {self.environment} environment"
                )
            if (
                not self.cirpass_session_token_secret
                or self.cirpass_session_token_secret == "dev-cirpass-session-secret-change-me"
            ):
                raise ValueError(
                    "cirpass_session_token_secret must be explicitly set in production/staging"
                )
        else:
            if not self.encryption_master_key:
                warnings.warn(
                    "encryption_master_key is empty — encrypted fields "
                    "will not work. Set it before deploying.",
                    UserWarning,
                    stacklevel=2,
                )
            if not self.dpp_signing_key:
                warnings.warn(
                    "dpp_signing_key is empty — published DPPs will not be signed.",
                    UserWarning,
                    stacklevel=2,
                )
            if self.cirpass_session_token_secret == "dev-cirpass-session-secret-change-me":
                warnings.warn(
                    "cirpass_session_token_secret uses development default. "
                    "Set a unique secret before deploying publicly.",
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
