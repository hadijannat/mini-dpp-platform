"""
DPP (Digital Product Passport) Core Service.
Handles DPP lifecycle, revision management, and data hydration.
"""

import json
from datetime import UTC, datetime
from typing import Any
from typing import cast as typing_cast
from uuid import UUID

from jwt import api_jws
from jwt.exceptions import PyJWTError
from sqlalchemy import String, false, func, or_, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.crypto.canonicalization import (
    CANONICALIZATION_RFC8785,
    SHA256_ALGORITHM,
    sha256_hex_for_canonicalization,
)
from app.core.encryption import ConnectorConfigEncryptor, DPPFieldEncryptor, EncryptionError
from app.core.identifiers import (
    IdentifierValidationError,
    build_global_asset_id,
    normalize_base_uri,
)
from app.core.logging import get_logger
from app.core.settings_service import SettingsService
from app.db.models import (
    DPP,
    BatchImportJob,
    BatchImportJobItem,
    DataCarrier,
    DataCarrierIdentifierScheme,
    DataCarrierStatus,
    DPPRevision,
    DPPStatus,
    EncryptedValue,
    ResourceShare,
    RevisionState,
    Template,
    User,
    UserRole,
    VisibilityScope,
)
from app.modules.aas.conformance import validate_aas_environment
from app.modules.aas.sanitization import (
    SanitizationStats,
    sanitize_submodel_list_item_id_shorts,
)
from app.modules.aas.semantic_ids import (
    extract_normalized_semantic_ids,
    normalize_semantic_id,
)
from app.modules.compliance.service import ComplianceService
from app.modules.data_carriers.profile import (
    DATA_CARRIER_COMPLIANCE_PROFILE_KEY,
    DATA_CARRIER_PUBLISH_GATE_ENABLED_KEY,
    DataCarrierComplianceProfile,
    parse_data_carrier_compliance_profile,
)
from app.modules.dpps.basyx_builder import BasyxDppBuilder
from app.modules.dpps.canonical_patch import apply_canonical_patch
from app.modules.dpps.submodel_binding import (
    ResolvedSubmodelBinding,
    resolve_submodel_bindings,
)
from app.modules.qr.service import QRCodeService
from app.modules.templates.catalog import get_template_descriptor
from app.modules.templates.service import TemplateRegistryService

logger = get_logger(__name__)


class SigningError(Exception):
    """Raised when JWS signing is configured but fails."""


class AmbiguousSubmodelBindingError(ValueError):
    """Raised when a template key matches multiple submodels without an explicit target."""

    def __init__(self, template_key: str, submodel_ids: list[str]) -> None:
        self.template_key = template_key
        self.submodel_ids = submodel_ids
        quoted = ", ".join(submodel_ids)
        super().__init__(
            f"Ambiguous template binding for '{template_key}'. "
            f"Provide submodel_id. Candidates: {quoted}"
        )


class DPPService:
    """
    Core service for Digital Product Passport operations.

    Manages DPP creation, editing, publishing, and revision history.
    All edits create new revisions to maintain complete audit trails.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
        self._template_service = TemplateRegistryService(session)
        self._basyx_builder = BasyxDppBuilder(self._template_service)
        self._field_encryptor: DPPFieldEncryptor | None = None
        if self._settings.encryption_keyring:
            key_encryptor = ConnectorConfigEncryptor(
                self._settings.encryption_master_key,
                keyring=self._settings.encryption_keyring,
                active_key_id=self._settings.encryption_active_key_id,
            )
            self._field_encryptor = DPPFieldEncryptor(key_encryptor)

    @staticmethod
    def _is_aasd120_list_idshort_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return (
            "aasd-120" in message or "id_short may not be added to a submodelelementlist" in message
        )

    def _assert_conformant_environment(self, aas_env: dict[str, Any], *, context: str) -> None:
        validation = validate_aas_environment(aas_env)
        if not validation.is_valid:
            first_error = validation.errors[0] if validation.errors else "unknown validation error"
            raise ValueError(f"AAS conformance validation failed ({context}): {first_error}")
        if validation.warnings:
            logger.warning(
                "aas_conformance_warnings",
                context=context,
                warning_count=len(validation.warnings),
            )

    @staticmethod
    def _revision_manifest(revision: Any, field: str) -> dict[str, Any]:
        """Return a manifest dict from revision-like objects, defaulting safely for mocks/legacy data."""
        value = getattr(revision, field, None)
        return value if isinstance(value, dict) else {}

    async def _decrypt_revision_aas_env(self, revision: DPPRevision) -> dict[str, Any]:
        """Return revision AAS payload with encrypted markers resolved for internal operations."""
        field_encryptor: DPPFieldEncryptor | None = getattr(self, "_field_encryptor", None)
        wrapped_dek = getattr(revision, "wrapped_dek", None)
        kek_id = getattr(revision, "kek_id", None)
        if wrapped_dek and field_encryptor is None:
            raise ValueError("Encryption keyring is not configured for encrypted DPP revision")
        if field_encryptor is None or not wrapped_dek or not kek_id:
            return revision.aas_env_json
        result = await self._session.execute(
            select(EncryptedValue).where(EncryptedValue.revision_id == revision.id)
        )
        encrypted_rows = list(result.scalars().all())
        if not encrypted_rows:
            return revision.aas_env_json
        try:
            return field_encryptor.decrypt_for_read(
                revision.aas_env_json,
                tenant_id=revision.tenant_id,
                encrypted_rows=encrypted_rows,
                wrapped_dek=wrapped_dek,
                kek_id=kek_id,
                dek_wrapping_algorithm=getattr(revision, "dek_wrapping_algorithm", None),
            )
        except EncryptionError as exc:
            raise ValueError(f"Failed to decrypt encrypted revision payload: {exc}") from exc

    async def get_revision_aas_for_reader(self, revision: DPPRevision) -> dict[str, Any]:
        """Return reader-facing AAS payload with encrypted markers decrypted."""
        return await self._decrypt_revision_aas_env(revision)

    async def _prepare_revision_payload(
        self,
        *,
        tenant_id: UUID,
        aas_env: dict[str, Any],
    ) -> tuple[dict[str, Any], list[EncryptedValue], dict[str, Any]]:
        """Apply field-level encryption and digest metadata for a revision write."""
        stored_aas = aas_env
        encrypted_rows: list[EncryptedValue] = []
        wrapped_dek: str | None = None
        kek_id: str | None = None
        dek_wrapping_algorithm: str | None = None

        field_encryptor: DPPFieldEncryptor | None = getattr(self, "_field_encryptor", None)
        if field_encryptor is not None:
            encrypted = field_encryptor.prepare_for_storage(aas_env, tenant_id=tenant_id)
            stored_aas = encrypted.aas_env_json
            wrapped_dek = encrypted.wrapped_dek
            kek_id = encrypted.kek_id
            dek_wrapping_algorithm = encrypted.dek_wrapping_algorithm
            encrypted_rows = [
                EncryptedValue(
                    tenant_id=tenant_id,
                    id=item.ref_id,
                    revision_id=UUID(int=0),  # temporary placeholder, set after revision flush
                    json_pointer_path=item.json_pointer_path,
                    cipher_text=item.cipher_text,
                    key_id=item.key_id,
                    nonce=item.nonce,
                    algorithm=item.algorithm,
                )
                for item in encrypted.encrypted_fields
            ]
        elif self._aas_requires_field_encryption(aas_env):
            raise ValueError(
                "Confidentiality=encrypted elements require ENCRYPTION_KEYRING_JSON "
                "(or ENCRYPTION_MASTER_KEY fallback) to be configured"
            )

        digest = self._calculate_digest(stored_aas)
        metadata = {
            "digest_sha256": digest,
            "digest_algorithm": SHA256_ALGORITHM,
            "digest_canonicalization": CANONICALIZATION_RFC8785,
            "wrapped_dek": wrapped_dek,
            "kek_id": kek_id,
            "dek_wrapping_algorithm": dek_wrapping_algorithm,
        }
        return stored_aas, encrypted_rows, metadata

    def _aas_requires_field_encryption(self, aas_env: dict[str, Any]) -> bool:
        def _walk(node: Any) -> bool:
            if isinstance(node, dict):
                qualifiers = node.get("qualifiers")
                if isinstance(qualifiers, list):
                    for qualifier in qualifiers:
                        if not isinstance(qualifier, dict):
                            continue
                        if (
                            str(qualifier.get("type", "")).strip().lower() == "confidentiality"
                            and str(qualifier.get("value", "")).strip().lower() == "encrypted"
                            and node.get("value") is not None
                        ):
                            return True
                return any(_walk(value) for value in node.values())
            if isinstance(node, list):
                return any(_walk(item) for item in node)
            return False

        return _walk(aas_env)

    async def _ensure_user_exists(self, subject: str) -> User:
        """
        Ensure a user exists for the given OIDC subject.

        Auto-provisions users on first API access (just-in-time provisioning).
        """
        result = await self._session.execute(select(User).where(User.subject == subject))
        user = result.scalar_one_or_none()

        if user is None:
            # Auto-provision user with viewer role; access is enforced via ABAC/tenant roles.
            user = User(
                subject=subject,
                role=UserRole.VIEWER,
                attrs={},
            )
            self._session.add(user)
            await self._session.flush()
            logger.info("user_auto_provisioned", subject=subject)

        return user

    def resolve_required_specific_asset_ids(
        self,
        *,
        selected_templates: list[str] | None = None,
        profile_required_specific_asset_ids: list[str] | None = None,
    ) -> list[str]:
        """Resolve required specificAssetIds for DPP validation."""
        if profile_required_specific_asset_ids is not None:
            return self._normalize_required_asset_ids(profile_required_specific_asset_ids)

        resolved: list[str] = []
        seen: set[str] = set()
        default_required = getattr(
            self._settings,
            "dpp_required_specific_asset_ids_default",
            ["manufacturerPartId"],
        )
        if not isinstance(default_required, list):
            default_required = ["manufacturerPartId"]
        for name in default_required:
            normalized = str(name).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            resolved.append(normalized)

        by_template = (
            getattr(self._settings, "dpp_required_specific_asset_ids_by_template", {}) or {}
        )
        for template_key in selected_templates or []:
            required_for_template = by_template.get(template_key, [])
            if not isinstance(required_for_template, list):
                continue
            for name in required_for_template:
                normalized = str(name).strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                resolved.append(normalized)

        return resolved

    def _normalize_required_asset_ids(self, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = str(value).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            normalized.append(key)
        return normalized

    def _validate_required_specific_asset_ids(
        self,
        *,
        asset_ids: dict[str, Any],
        required_specific_asset_ids: list[str],
    ) -> None:
        missing = [
            key for key in required_specific_asset_ids if str(asset_ids.get(key, "")).strip() == ""
        ]
        if missing:
            joined = ", ".join(missing)
            raise IdentifierValidationError(f"Missing required specificAssetIds: {joined}")

    async def _load_data_carrier_publish_gate(
        self,
    ) -> tuple[bool, DataCarrierComplianceProfile]:
        """Load publish gate feature flag and compliance profile from settings."""
        settings_service = SettingsService(self._session)
        default_flag_raw = getattr(
            self._settings, "data_carrier_publish_gate_enabled_default", False
        )
        default_flag = default_flag_raw if isinstance(default_flag_raw, bool) else False
        gate_enabled = await settings_service.get_setting_bool(
            DATA_CARRIER_PUBLISH_GATE_ENABLED_KEY,
            default=default_flag,
        )
        stored_profile = await settings_service.get_setting_json(
            DATA_CARRIER_COMPLIANCE_PROFILE_KEY
        )
        profile = parse_data_carrier_compliance_profile(stored_profile)
        return gate_enabled, profile

    async def _assert_data_carrier_publish_gate(
        self,
        *,
        dpp_id: UUID,
        tenant_id: UUID,
    ) -> None:
        """Enforce optional data carrier gate before publish."""
        gate_enabled, profile = await self._load_data_carrier_publish_gate()
        if not gate_enabled:
            return

        result = await self._session.execute(
            select(DataCarrier).where(
                DataCarrier.tenant_id == tenant_id,
                DataCarrier.dpp_id == dpp_id,
            )
        )
        carriers = list(result.scalars().all())
        if not carriers:
            raise ValueError(
                "Publish blocked: data carrier gate requires at least one managed carrier"
            )

        allowed_types = {item.value for item in profile.allowed_carrier_types}
        allowed_levels = {item.value for item in profile.allowed_identity_levels}
        allowed_schemes = {item.value for item in profile.allowed_identifier_schemes}
        allowed_statuses = {item.value for item in profile.publish_allowed_statuses}

        for carrier in carriers:
            status_value = carrier.status.value
            if (
                profile.publish_require_active_carrier
                and carrier.status != DataCarrierStatus.ACTIVE
            ):
                continue
            if status_value not in allowed_statuses:
                continue
            if carrier.carrier_type.value not in allowed_types:
                continue
            if carrier.identity_level.value not in allowed_levels:
                continue
            if carrier.identifier_scheme.value not in allowed_schemes:
                continue
            if profile.publish_require_pre_sale_enabled and not carrier.pre_sale_enabled:
                continue
            if (
                profile.enforce_gtin_verified
                and carrier.identifier_scheme == DataCarrierIdentifierScheme.GS1_GTIN
                and not carrier.is_gtin_verified
            ):
                continue
            return

        raise ValueError(
            "Publish blocked: no data carrier satisfies the active compliance profile "
            f"('{profile.name}')"
        )

    async def create_dpp(
        self,
        tenant_id: UUID,
        tenant_slug: str,
        owner_subject: str,
        asset_ids: dict[str, Any],
        selected_templates: list[str],
        initial_data: dict[str, Any] | None = None,
        required_specific_asset_ids: list[str] | None = None,
    ) -> DPP:
        """
        Create a new DPP with initial draft revision.

        Args:
            owner_subject: OIDC subject of the creating user
            asset_ids: AAS specificAssetIds (manufacturerPartId, serialNumber, etc.)
            selected_templates: List of template keys to include
            initial_data: Optional initial values for submodel elements

        Returns:
            The created DPP with its first revision
        """
        # Ensure user exists (auto-provision if needed)
        await self._ensure_user_exists(owner_subject)

        required_asset_ids = self.resolve_required_specific_asset_ids(
            selected_templates=selected_templates,
            profile_required_specific_asset_ids=required_specific_asset_ids,
        )
        self._validate_required_specific_asset_ids(
            asset_ids=asset_ids,
            required_specific_asset_ids=required_asset_ids,
        )

        # Resolve globalAssetId if not provided (admin-managed base URI)
        settings_service = SettingsService(self._session)
        base_uri = await settings_service.get_setting("global_asset_id_base_uri")
        if not base_uri:
            base_uri = self._settings.global_asset_id_base_uri_default
        if base_uri:
            normalized_base = normalize_base_uri(base_uri)
            provided_global_id = str(asset_ids.get("globalAssetId", "")).strip()
            if provided_global_id:
                if not provided_global_id.startswith(normalized_base):
                    raise IdentifierValidationError(
                        "globalAssetId must start with the configured base URI."
                    )
            else:
                manufacturer_part_id = str(asset_ids.get("manufacturerPartId", "")).strip()
                if manufacturer_part_id:
                    asset_ids["globalAssetId"] = build_global_asset_id(normalized_base, asset_ids)

        # Build initial AAS Environment from selected templates
        aas_env = await self._build_initial_environment(
            asset_ids,
            selected_templates,
            initial_data or {},
        )

        # Create DPP record
        dpp = DPP(
            tenant_id=tenant_id,
            status=DPPStatus.DRAFT,
            owner_subject=owner_subject,
            asset_ids=asset_ids,
        )
        self._session.add(dpp)
        await self._session.flush()

        # Generate QR payload URL
        qr_service = QRCodeService()
        dpp.qr_payload = qr_service.build_dpp_url(
            str(dpp.id),
            tenant_slug=tenant_slug,
            short_link=False,
        )

        # Capture template provenance for audit trail
        template_provenance = await self._build_template_provenance(selected_templates)
        stored_aas, encrypted_rows, digest_metadata = await self._prepare_revision_payload(
            tenant_id=tenant_id,
            aas_env=aas_env,
        )

        # Create initial revision
        revision = DPPRevision(
            tenant_id=tenant_id,
            dpp_id=dpp.id,
            revision_no=1,
            state=RevisionState.DRAFT,
            aas_env_json=stored_aas,
            digest_sha256=digest_metadata["digest_sha256"],
            digest_algorithm=digest_metadata["digest_algorithm"],
            digest_canonicalization=digest_metadata["digest_canonicalization"],
            wrapped_dek=digest_metadata["wrapped_dek"],
            kek_id=digest_metadata["kek_id"],
            dek_wrapping_algorithm=digest_metadata["dek_wrapping_algorithm"],
            created_by_subject=owner_subject,
            template_provenance=template_provenance,
            supplementary_manifest={},
            doc_hints_manifest={},
        )
        self._session.add(revision)
        await self._session.flush()
        if encrypted_rows:
            for row in encrypted_rows:
                row.revision_id = revision.id
                self._session.add(row)
            await self._session.flush()

        logger.info(
            "dpp_created",
            dpp_id=str(dpp.id),
            owner=owner_subject,
            templates=selected_templates,
        )

        return dpp

    async def create_dpp_from_environment(
        self,
        tenant_id: UUID,
        tenant_slug: str,
        owner_subject: str,
        asset_ids: dict[str, Any],
        aas_env: dict[str, Any],
        required_specific_asset_ids: list[str] | None = None,
        supplementary_manifest: dict[str, Any] | None = None,
        doc_hints_manifest: dict[str, Any] | None = None,
    ) -> DPP:
        """
        Create a new DPP from a fully populated AAS environment.

        Used by import flows where the DPP JSON is provided externally.
        """
        await self._ensure_user_exists(owner_subject)

        required_asset_ids = self.resolve_required_specific_asset_ids(
            profile_required_specific_asset_ids=required_specific_asset_ids,
        )
        self._validate_required_specific_asset_ids(
            asset_ids=asset_ids,
            required_specific_asset_ids=required_asset_ids,
        )

        # Ensure globalAssetId if missing (same rules as regular create)
        settings_service = SettingsService(self._session)
        base_uri = await settings_service.get_setting("global_asset_id_base_uri")
        if not base_uri:
            base_uri = self._settings.global_asset_id_base_uri_default
        if base_uri:
            normalized_base = normalize_base_uri(base_uri)
            provided_global_id = str(asset_ids.get("globalAssetId", "")).strip()
            if provided_global_id:
                if not provided_global_id.startswith(normalized_base):
                    raise IdentifierValidationError(
                        "globalAssetId must start with the configured base URI."
                    )
            else:
                manufacturer_part_id = str(asset_ids.get("manufacturerPartId", "")).strip()
                if manufacturer_part_id:
                    asset_ids["globalAssetId"] = build_global_asset_id(normalized_base, asset_ids)

        stored_aas, encrypted_rows, digest_metadata = await self._prepare_revision_payload(
            tenant_id=tenant_id,
            aas_env=aas_env,
        )

        dpp = DPP(
            tenant_id=tenant_id,
            status=DPPStatus.DRAFT,
            owner_subject=owner_subject,
            asset_ids=asset_ids,
        )
        self._session.add(dpp)
        await self._session.flush()

        qr_service = QRCodeService()
        dpp.qr_payload = qr_service.build_dpp_url(
            str(dpp.id),
            tenant_slug=tenant_slug,
            short_link=False,
        )

        revision = DPPRevision(
            tenant_id=tenant_id,
            dpp_id=dpp.id,
            revision_no=1,
            state=RevisionState.DRAFT,
            aas_env_json=stored_aas,
            digest_sha256=digest_metadata["digest_sha256"],
            digest_algorithm=digest_metadata["digest_algorithm"],
            digest_canonicalization=digest_metadata["digest_canonicalization"],
            wrapped_dek=digest_metadata["wrapped_dek"],
            kek_id=digest_metadata["kek_id"],
            dek_wrapping_algorithm=digest_metadata["dek_wrapping_algorithm"],
            created_by_subject=owner_subject,
            template_provenance={},
            supplementary_manifest=supplementary_manifest or {},
            doc_hints_manifest=doc_hints_manifest or {},
        )
        self._session.add(revision)
        await self._session.flush()
        if encrypted_rows:
            for row in encrypted_rows:
                row.revision_id = revision.id
                self._session.add(row)
            await self._session.flush()

        logger.info("dpp_imported", dpp_id=str(dpp.id), owner=owner_subject)

        return dpp

    async def find_existing_dpp(
        self,
        tenant_id: UUID,
        asset_ids: dict[str, Any],
    ) -> DPP | None:
        manufacturer = str(asset_ids.get("manufacturerPartId", "")).strip()
        serial = str(asset_ids.get("serialNumber", "")).strip()
        global_asset_id = str(asset_ids.get("globalAssetId", "")).strip()

        query = select(DPP).where(DPP.tenant_id == tenant_id)
        if manufacturer and serial:
            query = query.where(
                DPP.asset_ids["manufacturerPartId"].astext == manufacturer,
                DPP.asset_ids["serialNumber"].astext == serial,
            )
        elif global_asset_id:
            query = query.where(DPP.asset_ids["globalAssetId"].astext == global_asset_id)
        else:
            return None

        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_dpp(
        self,
        dpp_id: UUID,
        tenant_id: UUID,
        include_revisions: bool = False,
    ) -> DPP | None:
        """
        Get a DPP by ID with optional revision history.
        """
        query = select(DPP).where(DPP.id == dpp_id, DPP.tenant_id == tenant_id)

        if include_revisions:
            query = query.options(selectinload(DPP.revisions))

        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_dpp_by_slug(
        self,
        slug: str,
        tenant_id: UUID,
    ) -> DPP | None:
        """
        Get a DPP by its short-link slug (first 8 hex chars of UUID).

        The slug is the first 8 characters of the UUID without hyphens,
        as generated by QRCodeService.build_dpp_url().
        """
        # Validate slug format (8 hex characters)
        if not slug or len(slug) != 8:
            return None
        slug = slug.lower()
        try:
            int(slug, 16)  # Validate hex
        except ValueError:
            return None

        # Query by UUID prefix using PostgreSQL text cast
        query = (
            select(DPP)
            .where(
                sql_cast(DPP.id, String).like(f"{slug[:8]}%"),
                DPP.tenant_id == tenant_id,
            )
            .limit(2)
        )

        result = await self._session.execute(query)
        matches = list(result.scalars().all())
        if len(matches) > 1:
            raise ValueError("Slug collision detected")
        return matches[0] if matches else None

    async def get_dpps_for_owner(
        self,
        tenant_id: UUID,
        owner_subject: str,
        status: DPPStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DPP]:
        """
        Get all DPPs owned by a specific user.
        """
        query = (
            select(DPP)
            .where(DPP.owner_subject == owner_subject, DPP.tenant_id == tenant_id)
            .order_by(DPP.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )

        if status:
            query = query.where(DPP.status == status)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count_dpps_for_tenant(
        self,
        tenant_id: UUID,
        status: DPPStatus | None = None,
    ) -> int:
        """Count all DPPs for a tenant (pre-ABAC)."""
        query = select(func.count()).select_from(DPP).where(DPP.tenant_id == tenant_id)
        if status:
            query = query.where(DPP.status == status)
        result = await self._session.execute(query)
        return result.scalar_one()

    async def get_shared_resource_ids(
        self,
        *,
        tenant_id: UUID,
        resource_type: str,
        user_subject: str,
    ) -> set[UUID]:
        """Get active shares for a user and resource type."""
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(ResourceShare.resource_id).where(
                ResourceShare.tenant_id == tenant_id,
                ResourceShare.resource_type == resource_type,
                ResourceShare.user_subject == user_subject,
                or_(
                    ResourceShare.expires_at.is_(None),
                    ResourceShare.expires_at > now,
                ),
            )
        )
        return set(result.scalars().all())

    async def is_resource_shared_with_user(
        self,
        *,
        tenant_id: UUID,
        resource_type: str,
        resource_id: UUID,
        user_subject: str,
    ) -> bool:
        """Check whether a specific resource is actively shared with a user."""
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(ResourceShare.id).where(
                ResourceShare.tenant_id == tenant_id,
                ResourceShare.resource_type == resource_type,
                ResourceShare.resource_id == resource_id,
                ResourceShare.user_subject == user_subject,
                or_(
                    ResourceShare.expires_at.is_(None),
                    ResourceShare.expires_at > now,
                ),
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_accessible_dpps(
        self,
        *,
        tenant_id: UUID,
        user_subject: str,
        is_tenant_admin: bool,
        status: DPPStatus | None = None,
        scope: str = "mine",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DPP], int, set[UUID]]:
        """
        List DPPs visible to the current tenant member with SQL prefiltering.

        Scope values:
        - mine: resources owned by caller
        - shared: resources shared to caller
        - all: all accessible resources (tenant admin sees all)
        """
        shared_ids = await self.get_shared_resource_ids(
            tenant_id=tenant_id,
            resource_type="dpp",
            user_subject=user_subject,
        )

        query = select(DPP).where(DPP.tenant_id == tenant_id)
        if status:
            query = query.where(DPP.status == status)

        if is_tenant_admin:
            if scope == "mine":
                query = query.where(DPP.owner_subject == user_subject)
            elif scope == "shared":
                if shared_ids:
                    query = query.where(
                        DPP.id.in_(shared_ids),
                        DPP.owner_subject != user_subject,
                    )
                else:
                    query = query.where(false())
        else:
            if scope == "mine":
                query = query.where(DPP.owner_subject == user_subject)
            elif scope == "shared":
                if shared_ids:
                    query = query.where(
                        DPP.id.in_(shared_ids),
                        DPP.owner_subject != user_subject,
                    )
                else:
                    query = query.where(false())
            else:
                access_conditions = [
                    DPP.owner_subject == user_subject,
                    DPP.visibility_scope == VisibilityScope.TENANT,
                ]
                if shared_ids:
                    access_conditions.append(DPP.id.in_(shared_ids))
                query = query.where(or_(*access_conditions))

        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self._session.execute(count_query)
        total_count = int(count_result.scalar_one())

        query = query.order_by(DPP.updated_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(query)
        return list(result.scalars().all()), total_count, shared_ids

    async def get_dpps_for_tenant(
        self,
        tenant_id: UUID,
        status: DPPStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DPP]:
        """Get all DPPs for a tenant."""
        query = (
            select(DPP)
            .where(DPP.tenant_id == tenant_id)
            .order_by(DPP.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )

        if status:
            query = query.where(DPP.status == status)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_published_dpps(
        self,
        tenant_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DPP]:
        """
        Get all published DPPs (viewer access).
        """
        query = (
            select(DPP)
            .where(DPP.status == DPPStatus.PUBLISHED, DPP.tenant_id == tenant_id)
            .order_by(DPP.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def create_batch_import_job(
        self,
        *,
        tenant_id: UUID,
        requested_by_subject: str,
        payload_hash: str,
        total: int,
    ) -> BatchImportJob:
        """Create a persisted batch import job."""
        job = BatchImportJob(
            tenant_id=tenant_id,
            requested_by_subject=requested_by_subject,
            payload_hash=payload_hash,
            total=total,
            succeeded=0,
            failed=0,
        )
        self._session.add(job)
        await self._session.flush()
        return job

    async def add_batch_import_item(
        self,
        *,
        tenant_id: UUID,
        job_id: UUID,
        item_index: int,
        status: str,
        dpp_id: UUID | None = None,
        error: str | None = None,
    ) -> BatchImportJobItem:
        """Persist one batch import item result."""
        item = BatchImportJobItem(
            tenant_id=tenant_id,
            job_id=job_id,
            item_index=item_index,
            status=status,
            dpp_id=dpp_id,
            error=error,
        )
        self._session.add(item)
        await self._session.flush()
        return item

    async def finalize_batch_import_job(
        self,
        *,
        job: BatchImportJob,
        succeeded: int,
        failed: int,
    ) -> BatchImportJob:
        """Update final counts for a persisted batch import job."""
        job.succeeded = succeeded
        job.failed = failed
        await self._session.flush()
        return job

    async def list_batch_import_jobs(
        self,
        *,
        tenant_id: UUID,
        requester_subject: str,
        is_tenant_admin: bool,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[BatchImportJob], int]:
        """List batch import jobs visible to current user."""
        query = select(BatchImportJob).where(BatchImportJob.tenant_id == tenant_id)
        if not is_tenant_admin:
            query = query.where(BatchImportJob.requested_by_subject == requester_subject)

        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self._session.execute(count_query)
        total_count = int(count_result.scalar_one())

        result = await self._session.execute(
            query.order_by(BatchImportJob.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all()), total_count

    async def get_batch_import_job(
        self,
        *,
        tenant_id: UUID,
        job_id: UUID,
    ) -> BatchImportJob | None:
        """Get a batch import job with its items."""
        result = await self._session.execute(
            select(BatchImportJob)
            .options(selectinload(BatchImportJob.items))
            .where(
                BatchImportJob.id == job_id,
                BatchImportJob.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_revision(self, dpp_id: UUID, tenant_id: UUID) -> DPPRevision | None:
        """
        Get the latest revision of a DPP (draft or published).
        """
        result = await self._session.execute(
            select(DPPRevision)
            .where(DPPRevision.dpp_id == dpp_id, DPPRevision.tenant_id == tenant_id)
            .order_by(DPPRevision.revision_no.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_published_revision(self, dpp_id: UUID, tenant_id: UUID) -> DPPRevision | None:
        """
        Get the current published revision of a DPP.
        """
        dpp = await self.get_dpp(dpp_id, tenant_id)
        if not dpp or not dpp.current_published_revision_id:
            return None

        result = await self._session.execute(
            select(DPPRevision).where(
                DPPRevision.id == dpp.current_published_revision_id,
                DPPRevision.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_revision_by_no(
        self, dpp_id: UUID, tenant_id: UUID, rev_no: int
    ) -> DPPRevision | None:
        """Get a specific revision by its revision number."""
        result = await self._session.execute(
            select(DPPRevision).where(
                DPPRevision.dpp_id == dpp_id,
                DPPRevision.tenant_id == tenant_id,
                DPPRevision.revision_no == rev_no,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _diff_json(
        old: Any, new: Any, path: str = ""
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Recursively diff two JSON-like structures, returning (added, removed, changed)."""
        added: list[dict[str, Any]] = []
        removed: list[dict[str, Any]] = []
        changed: list[dict[str, Any]] = []

        if isinstance(old, dict) and isinstance(new, dict):
            all_keys = set(old.keys()) | set(new.keys())
            for key in sorted(all_keys):
                child_path = f"{path}.{key}" if path else key
                if key not in old:
                    added.append(
                        {
                            "path": child_path,
                            "operation": "added",
                            "old_value": None,
                            "new_value": new[key],
                        }
                    )
                elif key not in new:
                    removed.append(
                        {
                            "path": child_path,
                            "operation": "removed",
                            "old_value": old[key],
                            "new_value": None,
                        }
                    )
                else:
                    a, r, c = DPPService._diff_json(old[key], new[key], child_path)
                    added.extend(a)
                    removed.extend(r)
                    changed.extend(c)
        elif old != new:
            if path:
                changed.append(
                    {
                        "path": path,
                        "operation": "changed",
                        "old_value": old,
                        "new_value": new,
                    }
                )

        return added, removed, changed

    async def diff_revisions(
        self,
        dpp_id: UUID,
        tenant_id: UUID,
        rev_a: int,
        rev_b: int,
    ) -> dict[str, Any]:
        """Compare two revisions of a DPP, returning structured diff."""
        revision_a = await self.get_revision_by_no(dpp_id, tenant_id, rev_a)
        if revision_a is None:
            raise ValueError(f"Revision {rev_a} not found")

        revision_b = await self.get_revision_by_no(dpp_id, tenant_id, rev_b)
        if revision_b is None:
            raise ValueError(f"Revision {rev_b} not found")

        old_env = revision_a.aas_env_json or {}
        new_env = revision_b.aas_env_json or {}

        added_list, removed_list, changed_list = self._diff_json(old_env, new_env)

        return {
            "from_rev": rev_a,
            "to_rev": rev_b,
            "added": added_list,
            "removed": removed_list,
            "changed": changed_list,
        }

    async def get_submodel_definition(
        self,
        dpp_id: UUID,
        tenant_id: UUID,
        template_key: str,
        revision_selector: str | None = None,
        revision_id: UUID | None = None,
    ) -> tuple[dict[str, Any], DPPRevision]:
        descriptor = get_template_descriptor(template_key)
        if descriptor is None:
            raise ValueError(f"Unknown template key: {template_key}")

        revision: DPPRevision | None = None
        if revision_id is not None:
            result = await self._session.execute(
                select(DPPRevision).where(
                    DPPRevision.id == revision_id,
                    DPPRevision.dpp_id == dpp_id,
                    DPPRevision.tenant_id == tenant_id,
                )
            )
            revision = result.scalar_one_or_none()
        elif revision_selector == "published":
            revision = await self.get_published_revision(dpp_id, tenant_id)
        else:
            revision = await self.get_latest_revision(dpp_id, tenant_id)

        if revision is None:
            raise ValueError("Requested revision not found")

        template = await self._template_service.get_template(template_key)
        if not template:
            raise ValueError(f"Template {template_key} not found")
        idta_version = template.idta_version

        try:
            definition = self._basyx_builder.build_submodel_definition(
                aas_env_json=revision.aas_env_json,
                template_key=template_key,
                semantic_id=descriptor.semantic_id,
                idta_version=idta_version,
            )
        except ValueError:
            available_templates = await self._template_service.get_all_templates()
            template_lookup = {
                candidate.template_key: candidate
                for candidate in available_templates
                if getattr(candidate, "template_key", None)
            }
            template_lookup[template.template_key] = template
            definition = self._template_service.generate_template_definition(
                template,
                template_lookup=template_lookup,
            )

        return definition, revision

    async def get_submodel_bindings(
        self,
        *,
        revision: DPPRevision | None,
    ) -> list[ResolvedSubmodelBinding]:
        """Resolve deterministic submodel bindings for a given revision."""
        if revision is None:
            return []
        templates = await self._template_service.get_all_templates()
        return resolve_submodel_bindings(
            aas_env_json=revision.aas_env_json,
            templates=templates,
            template_provenance=revision.template_provenance or {},
        )

    async def get_revision_publish_constraints(
        self,
        *,
        revision: DPPRevision | None,
    ) -> dict[str, Any]:
        """Compute required asset IDs and publish blockers for a revision."""
        if revision is None:
            required = self.resolve_required_specific_asset_ids(selected_templates=None)
            return {
                "required_specific_asset_ids": required,
                "missing_required_specific_asset_ids": [],
                "publish_blockers": [],
            }

        templates = await self._template_service.get_all_templates()
        bindings = resolve_submodel_bindings(
            aas_env_json=revision.aas_env_json,
            templates=templates,
            template_provenance=revision.template_provenance or {},
        )
        selected_templates = sorted(
            {binding.template_key for binding in bindings if binding.template_key}
        )
        required = self.resolve_required_specific_asset_ids(selected_templates=selected_templates)

        asset_ids: dict[str, Any] = {}
        try:
            # Parse specificAssetIds without re-applying required validation here.
            asset_ids = self.extract_asset_ids_from_environment(
                revision.aas_env_json,
                required_specific_asset_ids=[],
            )
        except Exception:
            asset_ids = {}

        missing_required = [key for key in required if str(asset_ids.get(key, "")).strip() == ""]

        publish_blockers: list[str] = []
        try:
            self._assert_revision_binding_compatibility(
                revision=revision,
                templates=templates,
                operation="publish",
                dpp_id=revision.dpp_id,
            )
        except ValueError as exc:
            publish_blockers.append(str(exc))

        try:
            await self._assert_publish_supported_nodes(revision=revision, templates=templates)
        except ValueError as exc:
            publish_blockers.append(str(exc))

        if missing_required:
            publish_blockers.append(
                "Missing required specificAssetIds: " + ", ".join(missing_required)
            )

        return {
            "required_specific_asset_ids": required,
            "missing_required_specific_asset_ids": missing_required,
            "publish_blockers": publish_blockers,
        }

    def audit_revision_binding_compatibility(
        self,
        *,
        revision: DPPRevision | None,
        templates: list[Template],
    ) -> dict[str, Any]:
        """Audit revision bindings for strict semantic matching safety."""
        if revision is None:
            return {"ok": True, "issues": []}

        aas_env = revision.aas_env_json if isinstance(revision.aas_env_json, dict) else {}
        submodels = aas_env.get("submodels", [])
        if not isinstance(submodels, list):
            return {
                "ok": False,
                "issues": [{"code": "invalid_aas_environment", "detail": "submodels_not_list"}],
            }

        issues: list[dict[str, Any]] = []
        bindings = resolve_submodel_bindings(
            aas_env_json=aas_env,
            templates=templates,
            template_provenance=revision.template_provenance or {},
        )
        strict_sources = {"semantic_exact", "semantic_alias", "provenance", "submodel_id"}
        for binding in bindings:
            if binding.template_key is None:
                issues.append(
                    {
                        "code": "unresolved_binding",
                        "submodel_id": binding.submodel_id,
                        "id_short": binding.id_short,
                        "binding_source": binding.binding_source,
                    }
                )
                continue
            if binding.binding_source in strict_sources:
                continue
            issues.append(
                {
                    "code": "non_strict_binding_source",
                    "submodel_id": binding.submodel_id,
                    "id_short": binding.id_short,
                    "template_key": binding.template_key,
                    "binding_source": binding.binding_source,
                }
            )

        return {"ok": len(issues) == 0, "issues": issues}

    def _assert_revision_binding_compatibility(
        self,
        *,
        revision: DPPRevision | None,
        templates: list[Template],
        operation: str,
        dpp_id: UUID,
    ) -> None:
        audit = self.audit_revision_binding_compatibility(revision=revision, templates=templates)
        if audit["ok"]:
            return
        issues = typing_cast(list[dict[str, Any]], audit["issues"])
        preview = "; ".join(
            f"{issue.get('code')}:{issue.get('submodel_id') or issue.get('id_short') or 'unknown'}"
            for issue in issues[:5]
        )
        raise ValueError(
            f"{operation} blocked for DPP {dpp_id}: strict binding audit failed ({preview})"
        )

    async def _assert_publish_supported_nodes(
        self,
        *,
        revision: DPPRevision,
        templates: list[Template],
    ) -> None:
        template_lookup = {template.template_key: template for template in templates}
        bindings = resolve_submodel_bindings(
            aas_env_json=revision.aas_env_json,
            templates=templates,
            template_provenance=revision.template_provenance or {},
        )
        blocked: list[dict[str, Any]] = []
        seen_template_keys: set[str] = set()
        for binding in bindings:
            template_key = binding.template_key
            if not template_key or template_key in seen_template_keys:
                continue
            seen_template_keys.add(template_key)
            template = template_lookup.get(template_key)
            if template is None:
                continue
            contract = self._template_service.generate_template_contract(
                template,
                template_lookup=template_lookup,
            )
            unsupported_nodes = contract.get("unsupported_nodes", [])
            if isinstance(unsupported_nodes, list) and unsupported_nodes:
                blocked.append(
                    {
                        "template_key": template_key,
                        "unsupported_count": len(unsupported_nodes),
                    }
                )

        if blocked:
            summary = ", ".join(
                f"{item['template_key']}({item['unsupported_count']})" for item in blocked
            )
            raise ValueError(
                "Publish blocked: unsupported template nodes detected for "
                f"{summary}. Save draft is allowed, publish is blocked until support is added."
            )

    async def update_submodel(
        self,
        dpp_id: UUID,
        tenant_id: UUID,
        template_key: str,
        submodel_data: dict[str, Any],
        updated_by_subject: str,
        rebuild_from_template: bool = False,
        submodel_id: str | None = None,
    ) -> DPPRevision:
        """Compatibility updater accepting value-object payloads."""
        current_revision = await self.get_latest_revision(dpp_id, tenant_id)
        if not current_revision:
            raise ValueError(f"DPP {dpp_id} not found")

        dpp = await self.get_dpp(dpp_id, tenant_id)
        if dpp and dpp.status == DPPStatus.ARCHIVED:
            raise ValueError("Cannot update an archived DPP")

        base_env = await self._decrypt_revision_aas_env(current_revision)
        if self._is_legacy_environment(base_env):
            raise ValueError(
                "Legacy AAS environment detected. Recreate this DPP after updating templates."
            )

        (
            template,
            available_templates,
            template_lookup,
            target_submodel_id,
        ) = await self._resolve_update_target(
            base_env=base_env,
            current_revision=current_revision,
            template_key=template_key,
            submodel_id=submodel_id,
        )

        if rebuild_from_template:
            return await self._update_submodel_via_rebuild(
                dpp_id=dpp_id,
                tenant_id=tenant_id,
                current_revision=current_revision,
                template_key=template_key,
                template=template,
                template_lookup=template_lookup,
                target_submodel_id=target_submodel_id,
                submodel_data=submodel_data,
                updated_by_subject=updated_by_subject,
                asset_ids=(dpp.asset_ids if dpp else {}),
            )

        generate_template_contract = getattr(
            self._template_service, "generate_template_contract", None
        )
        if not callable(generate_template_contract):
            logger.warning(
                "template_contract_generator_unavailable_fallback",
                template_key=template_key,
                dpp_id=str(dpp_id),
            )
            return await self._update_submodel_via_rebuild(
                dpp_id=dpp_id,
                tenant_id=tenant_id,
                current_revision=current_revision,
                template_key=template_key,
                template=template,
                template_lookup=template_lookup,
                target_submodel_id=target_submodel_id,
                submodel_data=submodel_data,
                updated_by_subject=updated_by_subject,
                asset_ids=(dpp.asset_ids if dpp else {}),
            )

        contract = generate_template_contract(
            template,
            template_lookup=template_lookup,
        )
        target_submodel = self._find_submodel_json_by_id(base_env, target_submodel_id)
        if target_submodel is None:
            raise ValueError(
                f"submodel_id '{target_submodel_id}' not found in current DPP environment"
            )
        current_data = self._extract_submodel_data(target_submodel)
        operations = self._build_patch_ops_from_form_payload(
            definition=contract.get("definition", {}),
            current_data=current_data,
            incoming_data=submodel_data,
        )
        return await self.patch_submodel(
            dpp_id=dpp_id,
            tenant_id=tenant_id,
            template_key=template_key,
            operations=operations,
            updated_by_subject=updated_by_subject,
            submodel_id=target_submodel_id,
            strict=True,
            base_revision_id=None,
            preloaded_contract=contract,
            preloaded_revision=current_revision,
            preloaded_templates=available_templates,
            preloaded_template_lookup=template_lookup,
        )

    async def patch_submodel(
        self,
        *,
        dpp_id: UUID,
        tenant_id: UUID,
        template_key: str,
        operations: list[dict[str, Any]],
        updated_by_subject: str,
        submodel_id: str | None = None,
        strict: bool = True,
        base_revision_id: UUID | None = None,
        preloaded_contract: dict[str, Any] | None = None,
        preloaded_revision: DPPRevision | None = None,
        preloaded_templates: list[Template] | None = None,
        preloaded_template_lookup: dict[str, Template] | None = None,
    ) -> DPPRevision:
        """Patch a submodel via canonical operations."""
        current_revision = preloaded_revision or await self.get_latest_revision(dpp_id, tenant_id)
        if not current_revision:
            raise ValueError(f"DPP {dpp_id} not found")
        if base_revision_id is not None and current_revision.id != base_revision_id:
            raise ValueError(
                f"Base revision mismatch: expected {base_revision_id}, latest is {current_revision.id}"
            )

        dpp = await self.get_dpp(dpp_id, tenant_id)
        if dpp and dpp.status == DPPStatus.ARCHIVED:
            raise ValueError("Cannot update an archived DPP")

        base_env = await self._decrypt_revision_aas_env(current_revision)
        if self._is_legacy_environment(base_env):
            raise ValueError(
                "Legacy AAS environment detected. Recreate this DPP after updating templates."
            )

        (
            template,
            available_templates,
            template_lookup,
            target_submodel_id,
        ) = await self._resolve_update_target(
            base_env=base_env,
            current_revision=current_revision,
            template_key=template_key,
            submodel_id=submodel_id,
            preloaded_templates=preloaded_templates,
            preloaded_template_lookup=preloaded_template_lookup,
        )

        contract = preloaded_contract or self._template_service.generate_template_contract(
            template,
            template_lookup=template_lookup,
        )
        patch_result = apply_canonical_patch(
            aas_env_json=base_env,
            submodel_id=target_submodel_id,
            operations=operations,
            contract=contract,
            strict=strict,
        )
        aas_env = patch_result.aas_env_json
        self._assert_conformant_environment(aas_env, context="patch_submodel")

        revision = await self._create_draft_revision(
            dpp_id=dpp_id,
            tenant_id=tenant_id,
            current_revision=current_revision,
            aas_env=aas_env,
            updated_by_subject=updated_by_subject,
            doc_hints_manifest=contract.get("doc_hints"),
        )

        logger.info(
            "submodel_patched",
            dpp_id=str(dpp_id),
            template_key=template_key,
            revision_no=revision.revision_no,
            operation_count=len(operations),
            strict=strict,
        )

        await self._cleanup_old_draft_revisions(dpp_id, tenant_id)
        return revision

    async def _resolve_update_target(
        self,
        *,
        base_env: dict[str, Any],
        current_revision: DPPRevision,
        template_key: str,
        submodel_id: str | None,
        preloaded_templates: list[Template] | None = None,
        preloaded_template_lookup: dict[str, Template] | None = None,
    ) -> tuple[Template, list[Template], dict[str, Template], str]:
        template = None
        if preloaded_template_lookup and template_key in preloaded_template_lookup:
            template = preloaded_template_lookup[template_key]
        if template is None:
            template = await self._template_service.get_template(template_key)
        if not template:
            try:
                template = await self._template_service.refresh_template(template_key)
            except Exception as exc:
                logger.warning(
                    "template_missing_and_refresh_failed",
                    template_key=template_key,
                    error=str(exc),
                )
                template = None
        if template is None:
            raise ValueError(f"Template {template_key} not found")

        available_templates = list(preloaded_templates or [])
        if not available_templates:
            get_all_templates = getattr(self._template_service, "get_all_templates", None)
            if callable(get_all_templates):
                available_templates = await get_all_templates()
            else:
                available_templates = [template]

        template_lookup = dict(preloaded_template_lookup or {})
        for candidate in available_templates:
            if getattr(candidate, "template_key", None):
                template_lookup[candidate.template_key] = candidate
        template_lookup[template.template_key] = template

        bindings = resolve_submodel_bindings(
            aas_env_json=base_env,
            templates=available_templates,
            template_provenance=current_revision.template_provenance or {},
        )
        if submodel_id is not None:
            existing_target = self._find_submodel_json_by_id(base_env, submodel_id)
            if existing_target is None:
                raise ValueError(
                    f"submodel_id '{submodel_id}' not found in current DPP environment"
                )

        matching_bindings = [
            binding for binding in bindings if binding.template_key == template_key
        ]
        target_submodel_id = submodel_id
        if target_submodel_id is not None:
            explicit_match = next(
                (
                    binding
                    for binding in matching_bindings
                    if binding.submodel_id == target_submodel_id
                ),
                None,
            )
            if explicit_match is None:
                raise ValueError(
                    f"Submodel '{target_submodel_id}' is not bound to template '{template_key}'"
                )
        elif len(matching_bindings) > 1:
            candidates = [
                binding.submodel_id or binding.id_short or "unknown-submodel"
                for binding in matching_bindings
            ]
            raise AmbiguousSubmodelBindingError(template_key=template_key, submodel_ids=candidates)
        elif len(matching_bindings) == 1:
            target_submodel_id = matching_bindings[0].submodel_id
        else:
            raise ValueError(f"No submodel in this DPP is bound to template '{template_key}'")
        if not target_submodel_id:
            raise ValueError(f"No concrete submodel_id resolved for template '{template_key}'")
        return template, available_templates, template_lookup, target_submodel_id

    async def _update_submodel_via_rebuild(
        self,
        *,
        dpp_id: UUID,
        tenant_id: UUID,
        current_revision: DPPRevision,
        template_key: str,
        template: Template,
        template_lookup: dict[str, Template],
        target_submodel_id: str,
        submodel_data: dict[str, Any],
        updated_by_subject: str,
        asset_ids: dict[str, Any],
    ) -> DPPRevision:
        base_env = await self._decrypt_revision_aas_env(current_revision)
        applied_autofix = False
        autofix_stats = SanitizationStats()
        try:
            aas_env = self._basyx_builder.update_submodel_environment(
                aas_env_json=base_env,
                template_key=template_key,
                template=template,
                submodel_data=submodel_data,
                asset_ids=asset_ids,
                rebuild_from_template=True,
                submodel_id=target_submodel_id,
                template_lookup=template_lookup,
            )
        except Exception as exc:
            if not self._is_aasd120_list_idshort_error(exc):
                raise ValueError(f"BaSyx update failed: {exc}") from exc
            sanitized_env, autofix_stats = sanitize_submodel_list_item_id_shorts(base_env)
            applied_autofix = True
            aas_env = self._basyx_builder.update_submodel_environment(
                aas_env_json=sanitized_env,
                template_key=template_key,
                template=template,
                submodel_data=submodel_data,
                asset_ids=asset_ids,
                rebuild_from_template=True,
                submodel_id=target_submodel_id,
                template_lookup=template_lookup,
            )

        self._assert_conformant_environment(aas_env, context="update_submodel_rebuild")
        revision = await self._create_draft_revision(
            dpp_id=dpp_id,
            tenant_id=tenant_id,
            current_revision=current_revision,
            aas_env=aas_env,
            updated_by_subject=updated_by_subject,
            doc_hints_manifest=self._revision_manifest(current_revision, "doc_hints_manifest"),
        )
        logger.info(
            "submodel_updated_rebuild",
            dpp_id=str(dpp_id),
            template_key=template_key,
            revision_no=revision.revision_no,
            applied_autofix=applied_autofix,
            lists_scanned=autofix_stats.lists_scanned,
            idshort_removed=autofix_stats.idshort_removed,
        )
        await self._cleanup_old_draft_revisions(dpp_id, tenant_id)
        return revision

    async def _create_draft_revision(
        self,
        *,
        dpp_id: UUID,
        tenant_id: UUID,
        current_revision: DPPRevision,
        aas_env: dict[str, Any],
        updated_by_subject: str,
        doc_hints_manifest: dict[str, Any] | None,
    ) -> DPPRevision:
        stored_aas, encrypted_rows, digest_metadata = await self._prepare_revision_payload(
            tenant_id=tenant_id,
            aas_env=aas_env,
        )
        new_revision_no = current_revision.revision_no + 1
        revision = DPPRevision(
            tenant_id=tenant_id,
            dpp_id=dpp_id,
            revision_no=new_revision_no,
            state=RevisionState.DRAFT,
            aas_env_json=stored_aas,
            digest_sha256=digest_metadata["digest_sha256"],
            digest_algorithm=digest_metadata["digest_algorithm"],
            digest_canonicalization=digest_metadata["digest_canonicalization"],
            wrapped_dek=digest_metadata["wrapped_dek"],
            kek_id=digest_metadata["kek_id"],
            dek_wrapping_algorithm=digest_metadata["dek_wrapping_algorithm"],
            created_by_subject=updated_by_subject,
            template_provenance=current_revision.template_provenance or {},
            supplementary_manifest=self._revision_manifest(
                current_revision, "supplementary_manifest"
            ),
            doc_hints_manifest=doc_hints_manifest,
        )
        self._session.add(revision)
        await self._session.flush()
        if encrypted_rows:
            for row in encrypted_rows:
                row.revision_id = revision.id
                self._session.add(row)
            await self._session.flush()
        return revision

    def _build_patch_ops_from_form_payload(
        self,
        *,
        definition: dict[str, Any],
        current_data: dict[str, Any],
        incoming_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        operations: list[dict[str, Any]] = []
        submodel = definition.get("submodel")
        if not isinstance(submodel, dict):
            return operations
        roots = submodel.get("elements")
        if not isinstance(roots, list):
            return operations
        for node in roots:
            if not isinstance(node, dict):
                continue
            id_short = node.get("idShort")
            if not isinstance(id_short, str) or id_short not in incoming_data:
                continue
            self._build_node_patch_ops(
                node=node,
                current_value=current_data.get(id_short),
                incoming_value=incoming_data.get(id_short),
                path=id_short,
                operations=operations,
            )
        return operations

    def _build_node_patch_ops(
        self,
        *,
        node: dict[str, Any],
        current_value: Any,
        incoming_value: Any,
        path: str,
        operations: list[dict[str, Any]],
    ) -> None:
        model_type = str(node.get("modelType") or "")
        if model_type == "SubmodelElementCollection":
            if not isinstance(incoming_value, dict):
                return
            for child in node.get("children", []):
                if not isinstance(child, dict):
                    continue
                child_id_short = child.get("idShort")
                if not isinstance(child_id_short, str) or child_id_short not in incoming_value:
                    continue
                next_current = (
                    current_value.get(child_id_short) if isinstance(current_value, dict) else None
                )
                self._build_node_patch_ops(
                    node=child,
                    current_value=next_current,
                    incoming_value=incoming_value.get(child_id_short),
                    path=f"{path}/{child_id_short}",
                    operations=operations,
                )
            return

        if model_type == "SubmodelElementList":
            if not isinstance(incoming_value, list):
                return
            current_list = current_value if isinstance(current_value, list) else []
            item_node = node.get("items") if isinstance(node.get("items"), dict) else None
            for idx in range(len(current_list) - 1, len(incoming_value) - 1, -1):
                operations.append({"op": "remove_list_item", "path": path, "index": idx})
            if item_node:
                shared = min(len(current_list), len(incoming_value))
                for idx in range(shared):
                    self._build_node_patch_ops(
                        node=item_node,
                        current_value=current_list[idx],
                        incoming_value=incoming_value[idx],
                        path=f"{path}/{idx}",
                        operations=operations,
                    )
            for idx in range(len(current_list), len(incoming_value)):
                payload = incoming_value[idx]
                if not isinstance(payload, dict):
                    payload = {"value": payload}
                operations.append({"op": "add_list_item", "path": path, "value": payload})
            return

        if model_type == "MultiLanguageProperty":
            if incoming_value != current_value and isinstance(incoming_value, dict):
                operations.append({"op": "set_multilang", "path": path, "value": incoming_value})
            return

        if model_type in {"File", "Blob"}:
            if incoming_value != current_value and isinstance(incoming_value, dict):
                payload = {
                    "contentType": incoming_value.get("contentType"),
                    "url": incoming_value.get("value"),
                }
                operations.append({"op": "set_file_ref", "path": path, "value": payload})
            return

        if incoming_value != current_value:
            operations.append({"op": "set_value", "path": path, "value": incoming_value})

    async def refresh_and_rebuild_dpp_submodels(
        self,
        *,
        dpp_id: UUID,
        tenant_id: UUID,
        updated_by_subject: str,
    ) -> dict[str, Any]:
        """Refresh templates and rebuild all bound submodels for a single DPP."""
        current_revision = await self.get_latest_revision(dpp_id, tenant_id)
        if current_revision is None:
            raise ValueError(f"DPP {dpp_id} not found")

        dpp = await self.get_dpp(dpp_id, tenant_id)
        if dpp is None:
            raise ValueError(f"DPP {dpp_id} not found")
        if dpp.status == DPPStatus.ARCHIVED:
            raise ValueError("Cannot rebuild an archived DPP")

        refreshed_templates, _ = await self._template_service.refresh_all_templates()
        self._assert_revision_binding_compatibility(
            revision=current_revision,
            templates=refreshed_templates,
            operation="refresh_rebuild",
            dpp_id=dpp_id,
        )
        current_plain_env = await self._decrypt_revision_aas_env(current_revision)
        bindings = resolve_submodel_bindings(
            aas_env_json=current_plain_env,
            templates=refreshed_templates,
            template_provenance=current_revision.template_provenance or {},
        )

        summary: dict[str, Any] = {
            "attempted": 0,
            "succeeded": [],
            "failed": [],
            "skipped": [],
        }

        seen_submodels: set[str] = set()
        for binding in bindings:
            if current_revision is None:
                raise ValueError("Failed to reload revision during refresh-rebuild")

            submodel_label = binding.id_short or binding.submodel_id or "submodel"
            if not binding.submodel_id:
                summary["skipped"].append(
                    {
                        "submodel": submodel_label,
                        "reason": "missing_submodel_id",
                    }
                )
                continue

            if binding.submodel_id in seen_submodels:
                continue
            seen_submodels.add(binding.submodel_id)

            if not binding.template_key:
                summary["skipped"].append(
                    {
                        "submodel": submodel_label,
                        "reason": "no_matching_template",
                    }
                )
                continue

            submodel = self._find_submodel_json_by_id(
                current_plain_env,
                binding.submodel_id,
            )
            if submodel is None:
                summary["skipped"].append(
                    {
                        "submodel": submodel_label,
                        "reason": "submodel_not_found",
                    }
                )
                continue

            summary["attempted"] += 1
            submodel_data = self._extract_submodel_data(submodel)
            try:
                await self.update_submodel(
                    dpp_id=dpp_id,
                    tenant_id=tenant_id,
                    template_key=binding.template_key,
                    submodel_data=submodel_data,
                    updated_by_subject=updated_by_subject,
                    rebuild_from_template=True,
                    submodel_id=binding.submodel_id,
                )
                summary["succeeded"].append(
                    {
                        "template_key": binding.template_key,
                        "submodel_id": binding.submodel_id,
                        "submodel": submodel_label,
                    }
                )
                current_revision = await self.get_latest_revision(dpp_id, tenant_id)
                if current_revision is None:
                    raise ValueError("Failed to reload revision after rebuild")
                current_plain_env = await self._decrypt_revision_aas_env(current_revision)
            except Exception as exc:
                summary["failed"].append(
                    {
                        "template_key": binding.template_key,
                        "submodel_id": binding.submodel_id,
                        "submodel": submodel_label,
                        "error": str(exc),
                    }
                )

        return summary

    async def rebuild_all_from_templates(
        self,
        tenant_id: UUID,
        updated_by_subject: str,
    ) -> dict[str, Any]:
        """
        Rebuild all DPP submodels from the latest templates.

        Creates a new draft revision per DPP when changes are applied.
        """
        templates = await self._template_service.get_all_templates()
        if not templates:
            templates, _ = await self._template_service.refresh_all_templates()

        result = await self._session.execute(select(DPP).where(DPP.tenant_id == tenant_id))
        dpps = list(result.scalars().all())

        summary: dict[str, Any] = {
            "total": len(dpps),
            "updated": 0,
            "skipped": 0,
            "errors": [],
        }

        for dpp in dpps:
            try:
                updated = await self._rebuild_dpp_from_templates(
                    dpp,
                    templates,
                    updated_by_subject,
                )
                if updated:
                    summary["updated"] += 1
                else:
                    summary["skipped"] += 1
            except Exception as exc:  # pragma: no cover - defensive
                summary["errors"].append(
                    {
                        "dpp_id": dpp.id,
                        "error": str(exc),
                    }
                )
                summary["skipped"] += 1

        return summary

    async def repair_invalid_list_item_id_shorts(
        self,
        *,
        tenant_id: UUID,
        updated_by_subject: str,
        dry_run: bool = False,
        dpp_ids: list[UUID] | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Repair latest revisions that violate AASd-120 list-item idShort rules."""
        query = select(DPP).where(DPP.tenant_id == tenant_id)
        if dpp_ids:
            query = query.where(DPP.id.in_(dpp_ids))
        else:
            query = query.where(DPP.status != DPPStatus.ARCHIVED)
        query = query.order_by(DPP.updated_at.desc())
        if limit is not None:
            query = query.limit(limit)

        result = await self._session.execute(query)
        dpps = list(result.scalars().all())

        summary: dict[str, Any] = {
            "total": len(dpps),
            "repaired": 0,
            "skipped": 0,
            "errors": [],
            "dry_run": dry_run,
            "stats": {
                "lists_scanned": 0,
                "items_scanned": 0,
                "idshort_removed": 0,
                "paths_changed": 0,
            },
        }

        for dpp in dpps:
            try:
                current_revision = await self.get_latest_revision(dpp.id, tenant_id)
                if current_revision is None:
                    summary["skipped"] += 1
                    continue

                aas_env_json = await self._decrypt_revision_aas_env(current_revision)
                try:
                    self._basyx_builder._load_environment(aas_env_json)  # noqa: SLF001
                    summary["skipped"] += 1
                    continue
                except Exception as parse_exc:
                    if not self._is_aasd120_list_idshort_error(parse_exc):
                        summary["errors"].append(
                            {
                                "dpp_id": dpp.id,
                                "reason": f"parse_failed:{parse_exc}",
                            }
                        )
                        summary["skipped"] += 1
                        continue

                sanitized_env, stats = sanitize_submodel_list_item_id_shorts(aas_env_json)
                summary["stats"]["lists_scanned"] += stats.lists_scanned
                summary["stats"]["items_scanned"] += stats.items_scanned
                summary["stats"]["idshort_removed"] += stats.idshort_removed
                summary["stats"]["paths_changed"] += len(stats.paths_changed)

                if stats.idshort_removed == 0:
                    summary["skipped"] += 1
                    continue

                self._assert_conformant_environment(sanitized_env, context="repair_invalid_lists")

                if dry_run:
                    summary["repaired"] += 1
                    continue

                stored_aas, encrypted_rows, digest_metadata = await self._prepare_revision_payload(
                    tenant_id=tenant_id,
                    aas_env=sanitized_env,
                )
                new_revision_no = current_revision.revision_no + 1
                revision = DPPRevision(
                    tenant_id=tenant_id,
                    dpp_id=dpp.id,
                    revision_no=new_revision_no,
                    state=RevisionState.DRAFT,
                    aas_env_json=stored_aas,
                    digest_sha256=digest_metadata["digest_sha256"],
                    digest_algorithm=digest_metadata["digest_algorithm"],
                    digest_canonicalization=digest_metadata["digest_canonicalization"],
                    wrapped_dek=digest_metadata["wrapped_dek"],
                    kek_id=digest_metadata["kek_id"],
                    dek_wrapping_algorithm=digest_metadata["dek_wrapping_algorithm"],
                    created_by_subject=updated_by_subject,
                    template_provenance=current_revision.template_provenance or {},
                    supplementary_manifest=self._revision_manifest(
                        current_revision, "supplementary_manifest"
                    ),
                    doc_hints_manifest=self._revision_manifest(
                        current_revision, "doc_hints_manifest"
                    ),
                )
                self._session.add(revision)
                await self._session.flush()
                if encrypted_rows:
                    for row in encrypted_rows:
                        row.revision_id = revision.id
                        self._session.add(row)
                    await self._session.flush()
                await self._cleanup_old_draft_revisions(dpp.id, tenant_id)
                summary["repaired"] += 1
            except Exception as exc:  # pragma: no cover - defensive
                summary["errors"].append({"dpp_id": dpp.id, "reason": str(exc)})
                summary["skipped"] += 1

        logger.info(
            "dpp_repair_invalid_lists_run",
            tenant_id=str(tenant_id),
            total=summary["total"],
            repaired=summary["repaired"],
            skipped=summary["skipped"],
            dry_run=dry_run,
            lists_scanned=summary["stats"]["lists_scanned"],
            items_scanned=summary["stats"]["items_scanned"],
            idshort_removed=summary["stats"]["idshort_removed"],
            paths_changed=summary["stats"]["paths_changed"],
        )
        return summary

    async def publish_dpp(
        self,
        dpp_id: UUID,
        tenant_id: UUID,
        published_by_subject: str,
    ) -> DPP:
        """
        Publish a DPP, making its current draft visible to viewers.

        Creates a published revision from the latest draft and updates
        the DPP status and current_published_revision_id.

        When ``compliance_check_on_publish`` is enabled, runs an ESPR
        compliance check first and blocks publish if critical violations
        are found (Contract C).
        """
        dpp = await self.get_dpp(dpp_id, tenant_id)
        if not dpp:
            raise ValueError(f"DPP {dpp_id} not found")

        if dpp.status == DPPStatus.ARCHIVED:
            raise ValueError("Cannot publish an archived DPP")

        # Optional data carrier pre-publish gate (Phase 3)
        await self._assert_data_carrier_publish_gate(dpp_id=dpp_id, tenant_id=tenant_id)

        # Compliance pre-publish gate (Contract C)
        if self._settings.compliance_check_on_publish:
            compliance_svc = ComplianceService(self._session)
            report = await compliance_svc.check_pre_publish(dpp_id, tenant_id)
            if not report.is_compliant:
                violations = report.summary.critical_violations
                raise ValueError(
                    f"Publish blocked: {violations} critical compliance "
                    f"violation(s) in category '{report.category}'"
                )

        # Get latest draft revision
        latest_revision = await self.get_latest_revision(dpp_id, tenant_id)
        if not latest_revision:
            raise ValueError(f"No revision found for DPP {dpp_id}")
        has_submodels = (
            isinstance(latest_revision.aas_env_json, dict)
            and isinstance(latest_revision.aas_env_json.get("submodels"), list)
            and len(latest_revision.aas_env_json.get("submodels", [])) > 0
        )
        if has_submodels:
            current_templates = await self._template_service.get_all_templates()
            self._assert_revision_binding_compatibility(
                revision=latest_revision,
                templates=current_templates,
                operation="publish",
                dpp_id=dpp_id,
            )
            await self._assert_publish_supported_nodes(
                revision=latest_revision,
                templates=current_templates,
            )

        if latest_revision.state == RevisionState.PUBLISHED:
            # Already published, create new revision
            latest_plain_aas = await self._decrypt_revision_aas_env(latest_revision)
            stored_aas, encrypted_rows, digest_metadata = await self._prepare_revision_payload(
                tenant_id=tenant_id,
                aas_env=latest_plain_aas,
            )
            signed_jws = self._sign_digest(digest_metadata["digest_sha256"])
            new_revision_no = latest_revision.revision_no + 1
            revision = DPPRevision(
                tenant_id=tenant_id,
                dpp_id=dpp_id,
                revision_no=new_revision_no,
                state=RevisionState.PUBLISHED,
                aas_env_json=stored_aas,
                digest_sha256=digest_metadata["digest_sha256"],
                digest_algorithm=digest_metadata["digest_algorithm"],
                digest_canonicalization=digest_metadata["digest_canonicalization"],
                wrapped_dek=digest_metadata["wrapped_dek"],
                kek_id=digest_metadata["kek_id"],
                dek_wrapping_algorithm=digest_metadata["dek_wrapping_algorithm"],
                signed_jws=signed_jws,
                created_by_subject=published_by_subject,
                template_provenance=latest_revision.template_provenance or {},
                supplementary_manifest=self._revision_manifest(
                    latest_revision, "supplementary_manifest"
                ),
                doc_hints_manifest=self._revision_manifest(latest_revision, "doc_hints_manifest"),
            )
            self._session.add(revision)
            await self._session.flush()
            if encrypted_rows:
                for row in encrypted_rows:
                    row.revision_id = revision.id
                    self._session.add(row)
                await self._session.flush()
        else:
            # Mark current draft as published
            signed_jws = self._sign_digest(latest_revision.digest_sha256)
            latest_revision.state = RevisionState.PUBLISHED
            latest_revision.signed_jws = signed_jws
            revision = latest_revision

        # Update DPP status and pointer
        dpp.status = DPPStatus.PUBLISHED
        dpp.current_published_revision_id = revision.id

        await self._session.flush()

        logger.info(
            "dpp_published",
            dpp_id=str(dpp_id),
            revision_no=revision.revision_no,
            published_by=published_by_subject,
        )

        return dpp

    async def _rebuild_dpp_from_templates(
        self,
        dpp: DPP,
        templates: list[Template],
        updated_by_subject: str,
    ) -> bool:
        current_revision = await self.get_latest_revision(dpp.id, dpp.tenant_id)
        if not current_revision:
            return False
        if self._is_legacy_environment(current_revision.aas_env_json):
            raise ValueError(
                "Legacy AAS environment detected. Recreate this DPP after updating templates."
            )
        self._assert_revision_binding_compatibility(
            revision=current_revision,
            templates=templates,
            operation="bulk_rebuild",
            dpp_id=dpp.id,
        )

        base_env = await self._decrypt_revision_aas_env(current_revision)
        applied_autofix = False
        autofix_stats = SanitizationStats()

        try:
            aas_env, changed = self._basyx_builder.rebuild_environment_from_templates(
                aas_env_json=base_env,
                templates=templates,
                asset_ids=dpp.asset_ids,
            )
        except Exception as exc:
            if not self._is_aasd120_list_idshort_error(exc):
                raise

            sanitized_env, autofix_stats = sanitize_submodel_list_item_id_shorts(base_env)
            applied_autofix = True
            logger.warning(
                "aasd120_autofix_applied",
                dpp_id=str(dpp.id),
                template_key="*",
                revision_no_base=current_revision.revision_no,
                lists_scanned=autofix_stats.lists_scanned,
                idshort_removed=autofix_stats.idshort_removed,
            )
            try:
                aas_env, changed = self._basyx_builder.rebuild_environment_from_templates(
                    aas_env_json=sanitized_env,
                    templates=templates,
                    asset_ids=dpp.asset_ids,
                )
                logger.info(
                    "aasd120_autofix_retry_success",
                    dpp_id=str(dpp.id),
                    template_key="*",
                    revision_no_base=current_revision.revision_no,
                    lists_scanned=autofix_stats.lists_scanned,
                    idshort_removed=autofix_stats.idshort_removed,
                )
            except Exception as retry_exc:
                logger.error(
                    "aasd120_autofix_retry_failed",
                    dpp_id=str(dpp.id),
                    template_key="*",
                    revision_no_base=current_revision.revision_no,
                    lists_scanned=autofix_stats.lists_scanned,
                    idshort_removed=autofix_stats.idshort_removed,
                    error=str(retry_exc),
                )
                raise
        if not changed:
            return False

        self._assert_conformant_environment(aas_env, context="rebuild_from_templates")

        stored_aas, encrypted_rows, digest_metadata = await self._prepare_revision_payload(
            tenant_id=dpp.tenant_id,
            aas_env=aas_env,
        )
        new_revision_no = current_revision.revision_no + 1

        revision = DPPRevision(
            tenant_id=dpp.tenant_id,
            dpp_id=dpp.id,
            revision_no=new_revision_no,
            state=RevisionState.DRAFT,
            aas_env_json=stored_aas,
            digest_sha256=digest_metadata["digest_sha256"],
            digest_algorithm=digest_metadata["digest_algorithm"],
            digest_canonicalization=digest_metadata["digest_canonicalization"],
            wrapped_dek=digest_metadata["wrapped_dek"],
            kek_id=digest_metadata["kek_id"],
            dek_wrapping_algorithm=digest_metadata["dek_wrapping_algorithm"],
            created_by_subject=updated_by_subject,
            template_provenance=await self._build_provenance_from_db_templates(templates),
            supplementary_manifest=self._revision_manifest(
                current_revision, "supplementary_manifest"
            ),
            doc_hints_manifest=self._revision_manifest(current_revision, "doc_hints_manifest"),
        )
        self._session.add(revision)
        await self._session.flush()
        if encrypted_rows:
            for row in encrypted_rows:
                row.revision_id = revision.id
                self._session.add(row)
            await self._session.flush()

        logger.info(
            "dpp_rebuilt_from_templates_basyx",
            dpp_id=str(dpp.id),
            revision_no=new_revision_no,
            applied_autofix=applied_autofix,
            lists_scanned=autofix_stats.lists_scanned,
            idshort_removed=autofix_stats.idshort_removed,
        )

        await self._cleanup_old_draft_revisions(dpp.id, dpp.tenant_id)
        return True

    async def archive_dpp(self, dpp_id: UUID, tenant_id: UUID) -> DPP:
        """
        Archive a DPP, marking it as no longer active.

        Only published DPPs can be archived.  Archiving a draft would
        skip the review/publish step, violating the intended lifecycle.
        """
        dpp = await self.get_dpp(dpp_id, tenant_id)
        if not dpp:
            raise ValueError(f"DPP {dpp_id} not found")

        if dpp.status == DPPStatus.DRAFT:
            raise ValueError("Cannot archive a draft DPP — publish it first")
        if dpp.status == DPPStatus.ARCHIVED:
            raise ValueError("DPP is already archived")

        dpp.status = DPPStatus.ARCHIVED
        await self._session.flush()

        logger.info("dpp_archived", dpp_id=str(dpp_id))

        return dpp

    async def _cleanup_old_draft_revisions(self, dpp_id: UUID, tenant_id: UUID) -> int:
        """Delete oldest draft revisions beyond the retention limit. Returns count deleted."""
        from sqlalchemy import delete

        max_drafts = self._settings.dpp_max_draft_revisions
        result = await self._session.execute(
            select(DPPRevision.id)
            .where(
                DPPRevision.dpp_id == dpp_id,
                DPPRevision.tenant_id == tenant_id,
                DPPRevision.state == RevisionState.DRAFT,
            )
            .order_by(DPPRevision.revision_no.desc())
            .offset(max_drafts)
        )
        old_ids = list(result.scalars().all())
        if old_ids:
            await self._session.execute(delete(DPPRevision).where(DPPRevision.id.in_(old_ids)))
        return len(old_ids)

    async def _build_initial_environment(
        self,
        asset_ids: dict[str, Any],
        selected_templates: list[str],
        initial_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build initial AAS Environment from selected templates.
        """
        return await self._basyx_builder.build_environment(
            asset_ids=asset_ids,
            selected_templates=selected_templates,
            initial_data=initial_data,
        )

    async def _build_template_provenance(self, template_keys: list[str]) -> dict[str, Any]:
        """Build provenance metadata for selected templates."""
        provenance: dict[str, Any] = {}
        for key in template_keys:
            descriptor = get_template_descriptor(key)
            if not descriptor:
                continue
            # Query for cached template record
            result = await self._session.execute(
                select(Template)
                .where(Template.template_key == key)
                .order_by(Template.fetched_at.desc())
                .limit(1)
            )
            template = result.scalar_one_or_none()
            provenance[key] = {
                "idta_version": f"{descriptor.baseline_major}.{descriptor.baseline_minor}",
                "semantic_id": descriptor.semantic_id,
                "resolved_version": template.resolved_version if template else None,
                "source_file_sha": template.source_file_sha if template else None,
                "source_file_path": template.source_file_path if template else None,
                "source_kind": template.source_kind if template else None,
                "selection_strategy": (template.selection_strategy if template else None),
            }
        return provenance

    async def _build_provenance_from_db_templates(
        self, templates: list[Template]
    ) -> dict[str, Any]:
        """Build fresh provenance from Template DB objects (used during rebuild)."""
        provenance: dict[str, Any] = {}
        for tmpl in templates:
            descriptor = get_template_descriptor(tmpl.template_key)
            provenance[tmpl.template_key] = {
                "idta_version": (
                    f"{descriptor.baseline_major}.{descriptor.baseline_minor}"
                    if descriptor
                    else tmpl.idta_version
                ),
                "semantic_id": descriptor.semantic_id if descriptor else None,
                "resolved_version": tmpl.resolved_version,
                "source_file_sha": tmpl.source_file_sha,
                "source_file_path": tmpl.source_file_path,
                "source_kind": tmpl.source_kind,
                "selection_strategy": tmpl.selection_strategy,
            }
        return provenance

    async def _build_initial_environment_legacy(
        self,
        asset_ids: dict[str, Any],
        selected_templates: list[str],
        initial_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Legacy JSON-based AAS Environment builder (fallback).
        """
        aas_env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [],
            "conceptDescriptions": [],
        }

        # Create Asset Administration Shell
        aas_id = f"urn:dpp:aas:{asset_ids.get('manufacturerPartId', 'unknown')}"

        aas: dict[str, Any] = {
            "id": aas_id,
            "idShort": f"DPP_{asset_ids.get('manufacturerPartId', 'Product')}",
            "assetInformation": {
                "assetKind": "Instance",
                "globalAssetId": asset_ids.get("globalAssetId", aas_id),
                "specificAssetIds": [
                    {"name": k, "value": str(v)}
                    for k, v in asset_ids.items()
                    if k != "globalAssetId"
                ],
            },
            "submodelRefs": [],
        }

        # Add submodels from selected templates
        for template_key in selected_templates:
            template = await self._template_service.get_template(template_key)
            if not template:
                try:
                    template = await self._template_service.refresh_template(template_key)
                except Exception as exc:
                    logger.warning(
                        "template_missing_and_refresh_failed",
                        template_key=template_key,
                        error=str(exc),
                    )
                    template = None
            if not template:
                logger.warning("template_not_found", template_key=template_key)
                continue

            # Clone template submodel(s)
            template_submodels = template.template_json.get("submodels", [])

            for sm_template in template_submodels:
                # Create instance from template
                submodel_id = (
                    f"urn:dpp:sm:{template_key}:{asset_ids.get('manufacturerPartId', 'unknown')}"
                )

                submodel = json.loads(json.dumps(sm_template))
                submodel["id"] = submodel_id

                # Apply initial data if provided
                if template_key in initial_data:
                    submodel = await self._hydrate_submodel(
                        submodel,
                        initial_data[template_key],
                    )

                aas_env["submodels"].append(submodel)

                # Add reference to AAS
                aas["submodelRefs"].append(
                    {
                        "type": "ModelReference",
                        "keys": [{"type": "Submodel", "value": submodel_id}],
                    }
                )

            # Include concept descriptions
            template_cds = template.template_json.get("conceptDescriptions", [])
            aas_env["conceptDescriptions"].extend(template_cds)

        aas_env["assetAdministrationShells"].append(aas)

        return aas_env

    def extract_asset_ids_from_environment(
        self,
        aas_env: dict[str, Any],
        *,
        required_specific_asset_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Extract asset identifiers from an AAS environment.

        Reads the first AssetAdministrationShell's assetInformation field.
        """
        shells = aas_env.get("assetAdministrationShells")
        if not isinstance(shells, list) or not shells:
            raise ValueError("assetAdministrationShells must contain at least one shell")

        shell = shells[0]
        if not isinstance(shell, dict):
            raise ValueError("assetAdministrationShells must contain object entries")

        asset_info = shell.get("assetInformation")
        if not isinstance(asset_info, dict):
            raise ValueError("assetInformation is required in the AAS environment")

        asset_ids: dict[str, Any] = {}

        global_asset_id = asset_info.get("globalAssetId")
        if global_asset_id is not None:
            asset_ids["globalAssetId"] = str(global_asset_id)

        specific_asset_ids = asset_info.get("specificAssetIds") or asset_info.get("specificAssetId")
        if isinstance(specific_asset_ids, list):
            for entry in specific_asset_ids:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name", "")).strip()
                if not name:
                    continue
                value = entry.get("value")
                asset_ids[name] = "" if value is None else str(value)

        required = self.resolve_required_specific_asset_ids(
            profile_required_specific_asset_ids=required_specific_asset_ids,
        )
        self._validate_required_specific_asset_ids(
            asset_ids=asset_ids,
            required_specific_asset_ids=required,
        )

        return asset_ids

    def _match_template_for_submodel(
        self,
        submodel: dict[str, Any],
        templates: list[Template],
    ) -> Template | None:
        normalized_submodel_semantics = set(extract_normalized_semantic_ids(submodel))
        if not normalized_submodel_semantics:
            return None

        matches: list[Template] = []
        for template in templates:
            template_semantic = normalize_semantic_id(template.semantic_id)
            if template_semantic and template_semantic in normalized_submodel_semantics:
                matches.append(template)

        if len(matches) > 1:
            raise ValueError(
                "Ambiguous template match for submodel semantics: "
                f"{sorted(normalized_submodel_semantics)}"
            )
        return matches[0] if matches else None

    def _select_template_submodel(
        self,
        template: Template,
    ) -> dict[str, Any] | None:
        template_submodels = template.template_json.get("submodels", [])
        candidates: list[dict[str, Any]] = []
        target_semantic = normalize_semantic_id(template.semantic_id)
        for candidate in template_submodels:
            candidate_semantics = set(extract_normalized_semantic_ids(candidate))
            if target_semantic and target_semantic in candidate_semantics:
                candidates.append(candidate)
        if len(candidates) > 1:
            raise ValueError(
                f"Ambiguous template payload for '{template.template_key}': multiple semantic "
                "matches found"
            )
        if len(candidates) == 1:
            return candidates[0]
        return template_submodels[0] if template_submodels else None

    def _is_legacy_environment(self, aas_env: dict[str, Any]) -> bool:
        shells = aas_env.get("assetAdministrationShells")
        if not shells or not isinstance(shells, list):
            return False
        first = shells[0]
        return isinstance(first, dict) and "modelType" not in first

    async def _migrate_legacy_environment(
        self,
        legacy_env: dict[str, Any],
        templates: list[Template],
        asset_ids: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError("Legacy environment migration is no longer supported.")

    async def _hydrate_submodel(
        self,
        submodel: dict[str, Any],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Hydrate a submodel with provided data values.

        Maps form data to AAS submodel element structure.
        """
        elements = submodel.get("submodelElements", [])

        hydrated_elements = self._hydrate_elements(elements, data)
        submodel["submodelElements"] = hydrated_elements

        return submodel

    def _find_submodel_json_by_id(
        self,
        aas_env_json: dict[str, Any],
        submodel_id: str,
    ) -> dict[str, Any] | None:
        submodels = aas_env_json.get("submodels")
        if not isinstance(submodels, list):
            return None
        for submodel in submodels:
            if not isinstance(submodel, dict):
                continue
            if str(submodel.get("id")) == submodel_id:
                return submodel
        return None

    def _extract_submodel_data(self, submodel: dict[str, Any]) -> dict[str, Any]:
        elements = submodel.get("submodelElements", [])
        return self._extract_elements(elements)

    def _extract_elements(self, elements: list[dict[str, Any]]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for element in elements:
            if not isinstance(element, dict):
                continue
            id_short = element.get("idShort")
            if not id_short:
                continue
            data[id_short] = self._extract_element_value(element)
        return data

    def _extract_element_value(self, element: dict[str, Any]) -> Any:
        raw_model_type = element.get("modelType", {})
        if isinstance(raw_model_type, dict):
            element_type = raw_model_type.get("name", "Property")
        else:
            element_type = str(raw_model_type)

        if element_type == "SubmodelElementCollection":
            return self._extract_elements(element.get("value", []))
        if element_type == "SubmodelElementList":
            items = element.get("value", [])
            if isinstance(items, list):
                return [
                    self._extract_element_value(item) if isinstance(item, dict) else item
                    for item in items
                ]
            return []
        if element_type == "MultiLanguageProperty":
            value = element.get("value", [])
            if isinstance(value, list):
                return {
                    entry.get("language"): entry.get("text", "")
                    for entry in value
                    if entry.get("language")
                }
            if isinstance(value, dict):
                return value
        if element_type == "Range":
            return {"min": element.get("min"), "max": element.get("max")}
        if element_type == "File":
            return {
                "contentType": element.get("contentType", ""),
                "value": element.get("value", ""),
            }
        if element_type == "Blob":
            return {
                "contentType": element.get("contentType", ""),
                "value": element.get("value", ""),
            }
        if element_type == "ReferenceElement":
            reference = element.get("value", {}) if isinstance(element.get("value"), dict) else {}
            return {
                "type": reference.get("type", "ModelReference"),
                "keys": reference.get("keys", []),
            }
        if element_type == "Entity":
            return {
                "entityType": element.get("entityType"),
                "globalAssetId": element.get("globalAssetId", ""),
                "statements": self._extract_elements(element.get("statements", [])),
            }
        if element_type == "RelationshipElement":
            return {
                "first": element.get("first"),
                "second": element.get("second"),
            }
        if element_type == "AnnotatedRelationshipElement":
            return {
                "first": element.get("first"),
                "second": element.get("second"),
                "annotations": self._extract_elements(element.get("annotations", [])),
            }

        return element.get("value")

    def _hydrate_elements(
        self,
        elements: list[dict[str, Any]],
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Recursively hydrate submodel elements with data values.
        """
        hydrated: list[dict[str, Any]] = []

        for element in elements:
            id_short = element.get("idShort", "")
            hydrated_element = json.loads(json.dumps(element))

            if id_short in data:
                hydrated_element = self._hydrate_element_value(hydrated_element, data[id_short])

            hydrated.append(hydrated_element)

        return hydrated

    def _build_list_item_template(self, element: dict[str, Any]) -> dict[str, Any] | None:
        type_value = element.get("typeValueListElement")
        if isinstance(type_value, dict):
            type_value = type_value.get("name")
        value_type = element.get("valueTypeListElement")

        if not type_value:
            return None

        template: dict[str, Any] = {
            "idShort": "Item",
            "modelType": {"name": type_value},
        }

        if value_type:
            template["valueType"] = value_type

        return template

    def _hydrate_list_items(
        self,
        element: dict[str, Any],
        values: list[Any],
    ) -> list[Any]:
        template_items = element.get("value", [])
        template_item = template_items[0] if template_items else None

        if template_item is None:
            template_item = self._build_list_item_template(element)

        if template_item is None:
            return values

        hydrated_items: list[Any] = []
        for item_value in values:
            item_template = json.loads(json.dumps(template_item))
            hydrated_items.append(self._hydrate_element_value(item_template, item_value))

        return hydrated_items

    def _hydrate_element_value(
        self,
        element: dict[str, Any],
        value: Any,
    ) -> dict[str, Any]:
        element_type = element.get("modelType", {}).get("name", "Property")

        if element_type == "Property":
            element["value"] = "" if value is None else str(value)
        elif element_type == "MultiLanguageProperty":
            if isinstance(value, dict):
                element["value"] = [
                    {"language": lang, "text": text} for lang, text in value.items()
                ]
        elif element_type == "SubmodelElementCollection":
            if isinstance(value, dict):
                nested = element.get("value", [])
                element["value"] = self._hydrate_elements(nested, value)
        elif element_type == "SubmodelElementList":
            if isinstance(value, list):
                element["value"] = self._hydrate_list_items(element, value)
        elif element_type == "Range":
            if isinstance(value, dict):
                element["min"] = value.get("min")
                element["max"] = value.get("max")
        elif element_type == "File" and isinstance(value, dict):
            element["contentType"] = value.get("contentType", "")
            element["value"] = value.get("value", "")
        elif element_type == "ReferenceElement" and isinstance(value, dict):
            element["value"] = {
                "type": value.get("type", "ModelReference"),
                "keys": value.get("keys", []),
            }
        elif element_type == "Entity" and isinstance(value, dict):
            element["entityType"] = value.get("entityType", element.get("entityType"))
            if value.get("globalAssetId") is not None:
                element["globalAssetId"] = value.get("globalAssetId")
            statements = element.get("statements", [])
            statement_data = value.get("statements", {})
            if isinstance(statement_data, dict):
                element["statements"] = self._hydrate_elements(statements, statement_data)
        elif element_type == "RelationshipElement" and isinstance(value, dict):
            if value.get("first") is not None:
                element["first"] = value.get("first")
            if value.get("second") is not None:
                element["second"] = value.get("second")
        elif element_type == "AnnotatedRelationshipElement" and isinstance(value, dict):
            if value.get("first") is not None:
                element["first"] = value.get("first")
            if value.get("second") is not None:
                element["second"] = value.get("second")
            annotations = element.get("annotations", [])
            annotation_data = value.get("annotations", {})
            if isinstance(annotation_data, dict):
                element["annotations"] = self._hydrate_elements(annotations, annotation_data)

        return element

    def _calculate_digest(
        self,
        aas_env: dict[str, Any],
        *,
        canonicalization: str = CANONICALIZATION_RFC8785,
    ) -> str:
        """
        Calculate SHA-256 digest of canonicalized AAS environment.

        Uses deterministic JSON serialization for consistent hashing.
        """
        return sha256_hex_for_canonicalization(
            aas_env,
            canonicalization=canonicalization,
        )

    def _sign_digest(self, digest: str) -> str | None:
        """
        Sign a SHA-256 digest using JWS (JSON Web Signature).

        Returns a compact JWS string, or None if no signing key is configured.
        The JWS payload is the hex digest string. The header includes a key ID
        (kid) for key rotation support.
        """
        signing_key = self._settings.dpp_signing_key
        if not signing_key:
            return None
        algorithm = self._settings.dpp_signing_algorithm
        kid = self._settings.dpp_signing_key_id
        try:
            return api_jws.encode(
                digest.encode("utf-8"),
                signing_key,
                algorithm=algorithm,
                headers={"kid": kid},
            )
        except Exception as exc:
            raise SigningError(f"JWS signing failed: {exc}") from exc

    @staticmethod
    def verify_jws(signed_jws: str, expected_digest: str, public_key: str) -> bool:
        """
        Verify a JWS signature against an expected digest.

        Args:
            signed_jws: The compact JWS string from a published revision
            expected_digest: The SHA-256 hex digest to verify against
            public_key: PEM-encoded public key (RSA or EC)

        Returns:
            True if the signature is valid and the payload matches the expected digest
        """
        try:
            payload = api_jws.decode(
                signed_jws,
                public_key,
                algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "EdDSA"],
            )
            return bool(payload.decode("utf-8") == expected_digest)
        except PyJWTError:
            return False
        except (ValueError, TypeError, KeyError):
            return False
