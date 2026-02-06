"""
SQLAlchemy ORM models for the DPP platform.
All models use UUIDv7 for primary keys to ensure time-ordered identifiers.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    type_annotation_map = {
        dict[str, Any]: JSONB,
    }


# =============================================================================
# Enums
# =============================================================================


class UserRole(str, PyEnum):
    """User roles for RBAC baseline."""

    VIEWER = "viewer"
    PUBLISHER = "publisher"
    ADMIN = "admin"


class DPPStatus(str, PyEnum):
    """DPP lifecycle status."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class RevisionState(str, PyEnum):
    """State of a DPP revision."""

    DRAFT = "draft"
    PUBLISHED = "published"


class MasterVersionStatus(str, PyEnum):
    """Lifecycle status for DPP master versions."""

    RELEASED = "released"
    DEPRECATED = "deprecated"


class PolicyType(str, PyEnum):
    """Type of access control policy."""

    ROUTE = "route"
    SUBMODEL = "submodel"
    ELEMENT = "element"


class PolicyEffect(str, PyEnum):
    """Effect of a policy rule."""

    ALLOW = "allow"
    DENY = "deny"
    MASK = "mask"
    HIDE = "hide"
    ENCRYPT_REQUIRED = "encrypt_required"


class ConnectorType(str, PyEnum):
    """Type of external connector."""

    CATENA_X = "catena_x"
    REST = "rest"
    FILE = "file"


class ConnectorStatus(str, PyEnum):
    """Status of a connector."""

    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class TenantStatus(str, PyEnum):
    """Lifecycle status for tenants."""

    ACTIVE = "active"
    DISABLED = "disabled"


class TenantRole(str, PyEnum):
    """Roles scoped to a tenant."""

    VIEWER = "viewer"
    PUBLISHER = "publisher"
    TENANT_ADMIN = "tenant_admin"


# =============================================================================
# Tenant Models
# =============================================================================


class Tenant(Base):
    """Tenant entity for multi-tenant isolation."""

    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        comment="URL-safe tenant identifier",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, values_callable=lambda e: [m.value for m in e]),
        default=TenantStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    members: Mapped[list["TenantMember"]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_tenants_slug", "slug"),
        Index("ix_tenants_status", "status"),
        UniqueConstraint("slug", name="uq_tenants_slug"),
    )


class TenantMember(Base):
    """Membership mapping between users and tenants."""

    __tablename__ = "tenant_members"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="OIDC subject identifier",
    )
    role: Mapped[TenantRole] = mapped_column(
        Enum(TenantRole, values_callable=lambda e: [m.value for m in e]),
        default=TenantRole.VIEWER,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_subject", name="uq_tenant_membership"),
        Index("ix_tenant_members_tenant_id", "tenant_id"),
        Index("ix_tenant_members_user_subject", "user_subject"),
    )


class TenantScopedMixin:
    """Mixin for tenant-scoped models."""

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


# =============================================================================
# User Model
# =============================================================================


class User(Base):
    """
    User entity representing authenticated principals.

    Stores OIDC subject identifiers and ABAC attributes.
    """

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    subject: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="OIDC subject identifier",
    )
    email: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda e: [m.value for m in e]),
        default=UserRole.VIEWER,
        nullable=False,
    )
    attrs: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        comment="ABAC attributes: org, bpn, scopes, clearance, etc.",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    owned_dpps: Mapped[list["DPP"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_users_subject", "subject"),
        Index("ix_users_email", "email"),
    )


# =============================================================================
# Platform Settings
# =============================================================================


class PlatformSetting(Base):
    """
    Platform-level key/value settings.

    Used for admin-managed configuration like identifier namespaces.
    """

    __tablename__ = "platform_settings"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(255),
        comment="OIDC subject that last updated this setting",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_platform_settings_key", "key"),
        UniqueConstraint("key", name="uq_platform_settings_key"),
    )


# =============================================================================
# DPP and Revision Models
# =============================================================================


class DPP(TenantScopedMixin, Base):
    """
    Digital Product Passport entity.

    Represents a single product passport with its lifecycle status
    and associated asset identifiers.
    """

    __tablename__ = "dpps"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    status: Mapped[DPPStatus] = mapped_column(
        Enum(DPPStatus, values_callable=lambda e: [m.value for m in e]),
        default=DPPStatus.DRAFT,
        nullable=False,
    )
    owner_subject: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.subject"),
        nullable=False,
    )
    asset_ids: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        comment="AAS specificAssetIds: manufacturerPartId, serialNumber, batchId, globalAssetId",
    )
    qr_payload: Mapped[str | None] = mapped_column(
        Text,
        comment="URL encoded in QR code for product identification",
    )
    current_published_revision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "dpp_revisions.id",
            name="fk_dpps_current_published_revision",
            use_alter=True,
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    owner: Mapped["User"] = relationship(back_populates="owned_dpps")
    revisions: Mapped[list["DPPRevision"]] = relationship(
        back_populates="dpp",
        foreign_keys="DPPRevision.dpp_id",
        cascade="all, delete-orphan",
        order_by="DPPRevision.revision_no.desc()",
    )
    current_published_revision: Mapped["DPPRevision | None"] = relationship(
        foreign_keys=[current_published_revision_id],
        post_update=True,
    )
    policies: Mapped[list["Policy"]] = relationship(
        back_populates="dpp",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_dpps_owner_subject", "owner_subject"),
        Index("ix_dpps_status", "status"),
        Index("ix_dpps_asset_ids", "asset_ids", postgresql_using="gin"),
        Index("ix_dpps_tenant_updated", "tenant_id", "updated_at"),
    )


class DPPRevision(TenantScopedMixin, Base):
    """
    Immutable revision of a DPP.

    Every edit creates a new revision, providing complete audit history
    and enabling rollback capabilities.
    """

    __tablename__ = "dpp_revisions"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    dpp_id: Mapped[UUID] = mapped_column(
        ForeignKey("dpps.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Monotonically increasing revision number",
    )
    state: Mapped[RevisionState] = mapped_column(
        Enum(RevisionState, values_callable=lambda e: [m.value for m in e]),
        default=RevisionState.DRAFT,
        nullable=False,
    )
    aas_env_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Complete AAS Environment (AAS + Submodels + ConceptDescriptions)",
    )
    digest_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of canonicalized AAS environment JSON",
    )
    signed_jws: Mapped[str | None] = mapped_column(
        Text,
        comment="JWS signature of the digest for integrity verification",
    )
    created_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    dpp: Mapped["DPP"] = relationship(
        back_populates="revisions",
        foreign_keys=[dpp_id],
    )
    encrypted_values: Mapped[list["EncryptedValue"]] = relationship(
        back_populates="revision",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("dpp_id", "revision_no", name="uq_dpp_revision_no"),
        Index("ix_dpp_revisions_dpp_id", "dpp_id"),
        Index("ix_dpp_revisions_state", "state"),
    )


class EncryptedValue(TenantScopedMixin, Base):
    """
    Encrypted field value storage for field-level encryption.

    Stores encrypted payloads separately from the AAS environment,
    allowing authorized decryption while maintaining security.
    """

    __tablename__ = "encrypted_values"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("dpp_revisions.id", ondelete="CASCADE"),
        nullable=False,
    )
    json_pointer_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="JSON Pointer (RFC 6901) path to the encrypted element",
    )
    cipher_text: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )
    key_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Identifier of the DEK used for encryption",
    )
    nonce: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )
    algorithm: Mapped[str] = mapped_column(
        String(50),
        default="AES-256-GCM",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    revision: Mapped["DPPRevision"] = relationship(back_populates="encrypted_values")

    __table_args__ = (
        UniqueConstraint("revision_id", "json_pointer_path", name="uq_encrypted_value_path"),
        Index("ix_encrypted_values_revision_id", "revision_id"),
    )


# =============================================================================
# Template Model
# =============================================================================


class Template(Base):
    """
    IDTA Submodel Template storage.

    Caches fetched templates with version pinning for stability.
    """

    __tablename__ = "templates"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    template_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Template identifier: digital-nameplate, carbon-footprint, etc.",
    )
    idta_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="IDTA published version: 3.0.1, 1.0.1, etc.",
    )
    semantic_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full semantic ID (IRI) of the template",
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    template_aasx: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        comment="Original AASX package bytes",
    )
    template_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Normalized AAS Environment JSON",
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("template_key", "idta_version", name="uq_template_key_version"),
        Index("ix_templates_template_key", "template_key"),
    )


# =============================================================================
# DPP Master Models
# =============================================================================


class DPPMaster(TenantScopedMixin, Base):
    """
    Product-level DPP master template.

    Stores a draft template JSON with placeholders and variable definitions.
    Released versions are stored in DPPMasterVersion for immutable snapshots.
    """

    __tablename__ = "dpp_masters"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    product_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Product identifier (e.g., manufacturerPartId or GTIN)",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    selected_templates: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        comment="Template keys used to build the draft template",
    )
    draft_template_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Draft AAS environment with placeholders ({{var}})",
    )
    draft_variables: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        comment="Draft variable definitions",
    )
    created_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_by_subject: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    versions: Mapped[list["DPPMasterVersion"]] = relationship(
        back_populates="master",
        cascade="all, delete-orphan",
        order_by="DPPMasterVersion.released_at.desc()",
    )

    __table_args__ = (
        Index("ix_dpp_masters_product_id", "product_id"),
        UniqueConstraint("tenant_id", "product_id", name="uq_dpp_masters_tenant_product"),
    )


class DPPMasterVersion(TenantScopedMixin, Base):
    """
    Immutable released version of a DPP master template.

    Versions are addressed via semantic versions and optional aliases (e.g., latest).
    """

    __tablename__ = "dpp_master_versions"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    master_id: Mapped[UUID] = mapped_column(
        ForeignKey("dpp_masters.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Semantic version string for this release",
    )
    status: Mapped[MasterVersionStatus] = mapped_column(
        Enum(MasterVersionStatus, values_callable=lambda e: [m.value for m in e]),
        default=MasterVersionStatus.RELEASED,
        nullable=False,
    )
    aliases: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        comment="Alias tags for this version (e.g., latest)",
    )
    template_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Released template JSON snapshot",
    )
    variables: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        comment="Released variable definitions with resolved paths",
    )
    released_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    released_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    deprecation_message: Mapped[str | None] = mapped_column(Text)

    master: Mapped["DPPMaster"] = relationship(back_populates="versions")
    alias_links: Mapped[list["DPPMasterAlias"]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("master_id", "version", name="uq_dpp_master_version"),
        Index("ix_dpp_master_versions_master", "master_id"),
    )


class DPPMasterAlias(TenantScopedMixin, Base):
    """
    Alias mapping for master versions.

    Enforces uniqueness of aliases per master (e.g., only one "latest").
    """

    __tablename__ = "dpp_master_aliases"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    master_id: Mapped[UUID] = mapped_column(
        ForeignKey("dpp_masters.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("dpp_master_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    alias: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    version: Mapped["DPPMasterVersion"] = relationship(back_populates="alias_links")

    __table_args__ = (
        UniqueConstraint("master_id", "alias", name="uq_dpp_master_alias"),
        Index("ix_dpp_master_aliases_master", "master_id"),
        Index("ix_dpp_master_aliases_alias", "alias"),
    )


# =============================================================================
# Policy Model
# =============================================================================


class Policy(TenantScopedMixin, Base):
    """
    ABAC access control policy.

    Policies can be global (dpp_id is NULL) or DPP-specific.
    Element-level policies use JSON Pointer paths for targeting.
    """

    __tablename__ = "policies"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    dpp_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dpps.id", ondelete="CASCADE"),
        comment="NULL for global policies, specific DPP ID for per-DPP policies",
    )
    policy_type: Mapped[PolicyType] = mapped_column(
        Enum(PolicyType, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    target: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Target specification: route path, submodel key, or JSON Pointer",
    )
    effect: Mapped[PolicyEffect] = mapped_column(
        Enum(PolicyEffect, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    rules: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="ABAC condition rules",
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Higher priority policies are evaluated first",
    )
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    dpp: Mapped["DPP | None"] = relationship(back_populates="policies")

    __table_args__ = (
        Index("ix_policies_dpp_id", "dpp_id"),
        Index("ix_policies_type_target", "policy_type", "target"),
    )


# =============================================================================
# Connector Model
# =============================================================================


class Connector(TenantScopedMixin, Base):
    """
    External connector configuration.

    Stores connection details for Catena-X DTR and optional EDC DSP endpoint metadata.
    """

    __tablename__ = "connectors"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    connector_type: Mapped[ConnectorType] = mapped_column(
        Enum(ConnectorType, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Connection configuration: endpoints, auth, mapping",
    )
    status: Mapped[ConnectorStatus] = mapped_column(
        Enum(ConnectorStatus, values_callable=lambda e: [m.value for m in e]),
        default=ConnectorStatus.DISABLED,
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_connectors_type", "connector_type"),
        Index("ix_connectors_status", "status"),
    )


# =============================================================================
# Audit Event Model
# =============================================================================


class AuditEvent(TenantScopedMixin, Base):
    """
    Audit log for security and compliance tracking.

    Records all significant actions for accountability and forensics.
    """

    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    subject: Mapped[str | None] = mapped_column(
        String(255),
        comment="OIDC subject of the actor (NULL for system events)",
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Action type: VIEW_DPP, EDIT_SUBMODEL, EXPORT_AASX, etc.",
    )
    resource_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    resource_id: Mapped[str | None] = mapped_column(String(255))
    decision: Mapped[str | None] = mapped_column(
        String(50),
        comment="Policy decision: allow, deny, mask, etc.",
    )
    policy_id: Mapped[UUID | None] = mapped_column(ForeignKey("policies.id"))
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_audit_events_subject", "subject"),
        Index("ix_audit_events_action", "action"),
        Index("ix_audit_events_resource", "resource_type", "resource_id"),
        Index("ix_audit_events_created_at", "created_at"),
    )
