"""
SQLAlchemy ORM models for the DPP platform.
All models use UUIDv7 for primary keys to ensure time-ordered identifiers.
"""

from datetime import date, datetime
from enum import Enum as PyEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Double,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
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


class LifecyclePhase(str, PyEnum):
    """Product lifecycle phase for digital thread events."""

    DESIGN = "design"
    MANUFACTURE = "manufacture"
    LOGISTICS = "logistics"
    DEPLOY = "deploy"
    OPERATE = "operate"
    MAINTAIN = "maintain"
    END_OF_LIFE = "end_of_life"


class EPCISEventType(str, PyEnum):
    """EPCIS 2.0 event type discriminator."""

    OBJECT = "ObjectEvent"
    AGGREGATION = "AggregationEvent"
    TRANSACTION = "TransactionEvent"
    TRANSFORMATION = "TransformationEvent"
    ASSOCIATION = "AssociationEvent"


class ConnectorType(str, PyEnum):
    """Type of external connector."""

    CATENA_X = "catena_x"
    REST = "rest"
    FILE = "file"
    EDC = "edc"


class ConnectorStatus(str, PyEnum):
    """Status of a connector."""

    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class VisibilityScope(str, PyEnum):
    """Visibility scope for tenant resources."""

    OWNER_TEAM = "owner_team"
    TENANT = "tenant"


class RoleRequestStatus(str, PyEnum):
    """Status of a role upgrade request."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class TenantStatus(str, PyEnum):
    """Lifecycle status for tenants."""

    ACTIVE = "active"
    DISABLED = "disabled"


class TenantRole(str, PyEnum):
    """Roles scoped to a tenant."""

    VIEWER = "viewer"
    PUBLISHER = "publisher"
    TENANT_ADMIN = "tenant_admin"


class DataspaceConnectorRuntime(str, PyEnum):
    """Supported dataspace connector runtimes."""

    EDC = "edc"
    CATENA_X_DTR = "catena_x_dtr"


class DataspacePolicyTemplateState(str, PyEnum):
    """Lifecycle state for dataspace policy templates."""

    DRAFT = "draft"
    APPROVED = "approved"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class DataspaceRunStatus(str, PyEnum):
    """Execution status for conformance runs."""

    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"


class DataCarrierIdentityLevel(str, PyEnum):
    """Identity granularity for a data carrier."""

    MODEL = "model"
    BATCH = "batch"
    ITEM = "item"


class DataCarrierIdentifierScheme(str, PyEnum):
    """Identifier scheme encoded by a data carrier."""

    GS1_GTIN = "gs1_gtin"
    IEC61406 = "iec61406"
    DIRECT_URL = "direct_url"


class DataCarrierType(str, PyEnum):
    """Carrier technology."""

    QR = "qr"
    DATAMATRIX = "datamatrix"
    NFC = "nfc"


class DataCarrierResolverStrategy(str, PyEnum):
    """Resolution behavior for carrier URIs."""

    DYNAMIC_LINKSET = "dynamic_linkset"
    DIRECT_PUBLIC_DPP = "direct_public_dpp"


class DataCarrierStatus(str, PyEnum):
    """Lifecycle state for data carriers."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    WITHDRAWN = "withdrawn"


class DataCarrierArtifactType(str, PyEnum):
    """Persisted carrier artifact format."""

    PNG = "png"
    SVG = "svg"
    PDF = "pdf"
    ZPL = "zpl"
    CSV = "csv"


class IdentifierEntityType(str, PyEnum):
    """Entity type covered by CEN identifier governance."""

    PRODUCT = "product"
    OPERATOR = "operator"
    FACILITY = "facility"


class IdentifierIssuanceModel(str, PyEnum):
    """Issuance model for identifier schemes."""

    ISSUING_AGENCY = "issuing_agency"
    SELF_ISSUED = "self_issued"
    HYBRID = "hybrid"


class ExternalIdentifierStatus(str, PyEnum):
    """Lifecycle status for canonicalized external identifiers."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    WITHDRAWN = "withdrawn"


class OPCUAAuthType(str, PyEnum):
    """Authentication method for OPC UA source connections."""

    ANONYMOUS = "anonymous"
    USERNAME_PASSWORD = "username_password"
    CERTIFICATE = "certificate"


class OPCUAConnectionStatus(str, PyEnum):
    """Health status of an OPC UA source connection."""

    DISABLED = "disabled"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"


class OPCUAMappingType(str, PyEnum):
    """Discriminator for how an OPC UA mapping is applied."""

    AAS_PATCH = "aas_patch"
    EPCIS_EVENT = "epcis_event"


class DPPBindingMode(str, PyEnum):
    """How an OPC UA mapping resolves to a target DPP."""

    BY_DPP_ID = "by_dpp_id"
    BY_ASSET_IDS = "by_asset_ids"
    BY_SERIAL_SCAN = "by_serial_scan"


class DataspacePublicationStatus(str, PyEnum):
    """Status of a dataspace publication job."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


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
    visibility_scope: Mapped[VisibilityScope] = mapped_column(
        Enum(VisibilityScope, values_callable=lambda e: [m.value for m in e]),
        default=VisibilityScope.OWNER_TEAM,
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
    attachments: Mapped[list["DPPAttachment"]] = relationship(
        back_populates="dpp",
        cascade="all, delete-orphan",
        order_by="DPPAttachment.created_at.desc()",
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
    digest_algorithm: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="sha-256",
        comment="Digest algorithm identifier",
    )
    digest_canonicalization: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="rfc8785",
        comment="Canonicalization method used before digesting",
    )
    signed_jws: Mapped[str | None] = mapped_column(
        Text,
        comment="JWS signature of the digest for integrity verification",
    )
    wrapped_dek: Mapped[str | None] = mapped_column(
        Text,
        comment="Envelope-wrapped DEK used for encrypted fields in this revision",
    )
    kek_id: Mapped[str | None] = mapped_column(
        String(255),
        comment="KEK identifier used to wrap wrapped_dek",
    )
    dek_wrapping_algorithm: Mapped[str | None] = mapped_column(
        String(64),
        comment="Algorithm identifier for DEK wrapping",
    )
    created_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    template_provenance: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Template version metadata captured at creation time",
    )
    supplementary_manifest: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Supplementary AASX files manifest mapped to tenant attachment records",
    )
    doc_hints_manifest: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Resolved deterministic documentation hints snapshot for this revision",
    )
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


class DPPAttachment(TenantScopedMixin, Base):
    """Attachment metadata stored in object storage and linked to a DPP."""

    __tablename__ = "dpp_attachments"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    dpp_id: Mapped[UUID] = mapped_column(
        ForeignKey("dpps.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    dpp: Mapped["DPP"] = relationship(back_populates="attachments")

    __table_args__ = (
        UniqueConstraint("tenant_id", "object_key", name="uq_dpp_attachment_object_key"),
        Index("ix_dpp_attachments_dpp_id", "dpp_id"),
        Index("ix_dpp_attachments_tenant_created", "tenant_id", "created_at"),
    )


class BatchImportJob(TenantScopedMixin, Base):
    """Persisted batch import execution metadata."""

    __tablename__ = "batch_import_jobs"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    requested_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    items: Mapped[list["BatchImportJobItem"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="BatchImportJobItem.item_index.asc()",
    )

    __table_args__ = (
        Index("ix_batch_import_jobs_tenant_created", "tenant_id", "created_at"),
        Index("ix_batch_import_jobs_requested_by", "requested_by_subject"),
    )


class BatchImportJobItem(TenantScopedMixin, Base):
    """Per-item result row for a persisted batch import job."""

    __tablename__ = "batch_import_job_items"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("batch_import_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    dpp_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dpps.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    job: Mapped["BatchImportJob"] = relationship(back_populates="items")

    __table_args__ = (
        Index("ix_batch_import_job_items_job", "job_id"),
        Index("ix_batch_import_job_items_tenant_job", "tenant_id", "job_id"),
        UniqueConstraint("job_id", "item_index", name="uq_batch_import_job_item_index"),
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
    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="",
        comment="Human-readable template label for UI display",
    )
    catalog_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="published",
        comment="Catalog status (published or deprecated)",
    )
    catalog_folder: Mapped[str | None] = mapped_column(
        Text,
        comment="Folder path under IDTA catalog root (excluding status/version)",
    )
    idta_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="IDTA published version: 3.0.1, 1.0.1, etc.",
    )
    resolved_version: Mapped[str | None] = mapped_column(
        String(20),
        comment="Resolved upstream version used when refreshing the template",
    )
    semantic_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full semantic ID (IRI) of the template",
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_repo_ref: Mapped[str | None] = mapped_column(
        String(255),
        comment="Git ref used for template resolution (branch/tag/sha)",
    )
    source_file_path: Mapped[str | None] = mapped_column(
        Text,
        comment="Resolved upstream file path in source repository",
    )
    source_file_sha: Mapped[str | None] = mapped_column(
        String(128),
        comment="Resolved upstream file blob SHA",
    )
    source_kind: Mapped[str | None] = mapped_column(
        String(16),
        comment="Resolved template source kind (json or aasx)",
    )
    selection_strategy: Mapped[str | None] = mapped_column(
        String(32),
        comment="Deterministic file selection strategy identifier",
    )
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
        Index("ix_templates_catalog_status", "catalog_status"),
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
    visibility_scope: Mapped[VisibilityScope] = mapped_column(
        Enum(VisibilityScope, values_callable=lambda e: [m.value for m in e]),
        default=VisibilityScope.OWNER_TEAM,
        nullable=False,
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


class DataspaceConnector(TenantScopedMixin, Base):
    """
    Tenant-scoped dataspace connector instance configuration.

    Stores non-secret runtime configuration and participant metadata.
    Secret values are stored separately in ``dataspace_connector_secrets``.
    """

    __tablename__ = "dataspace_connectors"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    runtime: Mapped[DataspaceConnectorRuntime] = mapped_column(
        Enum(DataspaceConnectorRuntime, values_callable=lambda e: [m.value for m in e]),
        default=DataspaceConnectorRuntime.EDC,
        nullable=False,
    )
    participant_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[ConnectorStatus] = mapped_column(
        Enum(ConnectorStatus, values_callable=lambda e: [m.value for m in e]),
        default=ConnectorStatus.DISABLED,
        nullable=False,
    )
    runtime_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Non-secret runtime configuration (URLs, IDs, capabilities)",
    )
    created_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_validation_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    secrets: Mapped[list["DataspaceConnectorSecret"]] = relationship(
        back_populates="connector",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_dataspace_connectors_tenant_name"),
        Index("ix_dataspace_connectors_runtime", "runtime"),
        Index("ix_dataspace_connectors_status", "status"),
    )


class DataspaceConnectorSecret(TenantScopedMixin, Base):
    """Encrypted secret material bound to a dataspace connector."""

    __tablename__ = "dataspace_connector_secrets"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    connector_id: Mapped[UUID] = mapped_column(
        ForeignKey("dataspace_connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    secret_ref: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Opaque secret reference used by runtime config fields",
    )
    encrypted_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Envelope encrypted secret value",
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

    connector: Mapped["DataspaceConnector"] = relationship(back_populates="secrets")

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "connector_id",
            "secret_ref",
            name="uq_dataspace_connector_secret_ref",
        ),
        Index("ix_dataspace_connector_secrets_connector", "connector_id"),
    )


class DataspacePolicyTemplate(TenantScopedMixin, Base):
    """Reusable usage-control policy templates for dataspace publication."""

    __tablename__ = "dataspace_policy_templates"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False, default="1")
    state: Mapped[DataspacePolicyTemplateState] = mapped_column(
        Enum(DataspacePolicyTemplateState, values_callable=lambda e: [m.value for m in e]),
        default=DataspacePolicyTemplateState.DRAFT,
        nullable=False,
    )
    policy: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Normalized policy payload used for runtime policy generation",
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    approved_by_subject: Mapped[str | None] = mapped_column(String(255))
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
        UniqueConstraint(
            "tenant_id",
            "name",
            "version",
            name="uq_dataspace_policy_templates_tenant_name_version",
        ),
        Index("ix_dataspace_policy_templates_state", "state"),
    )


class DataspaceAssetPublication(TenantScopedMixin, Base):
    """Published dataspace asset record for a DPP revision."""

    __tablename__ = "dataspace_asset_publications"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    dpp_id: Mapped[UUID] = mapped_column(
        ForeignKey("dpps.id", ondelete="CASCADE"),
        nullable=False,
    )
    connector_id: Mapped[UUID] = mapped_column(
        ForeignKey("dataspace_connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    policy_template_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dataspace_policy_templates.id", ondelete="SET NULL"),
    )
    revision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dpp_revisions.id", ondelete="SET NULL"),
    )
    asset_id: Mapped[str] = mapped_column(String(255), nullable=False)
    access_policy_id: Mapped[str | None] = mapped_column(String(255))
    usage_policy_id: Mapped[str | None] = mapped_column(String(255))
    contract_definition_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="published")
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
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
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_dataspace_asset_publications_idempotency",
        ),
        Index("ix_dataspace_asset_publications_dpp", "tenant_id", "dpp_id"),
        Index("ix_dataspace_asset_publications_connector", "connector_id"),
        Index("ix_dataspace_asset_publications_asset", "asset_id"),
    )


class DataspaceNegotiation(TenantScopedMixin, Base):
    """Negotiation state tracking for dataspace contract negotiations."""

    __tablename__ = "dataspace_negotiations"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    connector_id: Mapped[UUID] = mapped_column(
        ForeignKey("dataspace_connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    publication_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dataspace_asset_publications.id", ondelete="SET NULL"),
    )
    negotiation_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Runtime negotiation ID (e.g., EDC @id)",
    )
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    contract_agreement_id: Mapped[str | None] = mapped_column(String(255))
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
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
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_dataspace_negotiations_idempotency",
        ),
        Index("ix_dataspace_negotiations_connector", "connector_id"),
        Index("ix_dataspace_negotiations_external_id", "negotiation_id"),
    )


class DataspaceTransfer(TenantScopedMixin, Base):
    """Transfer process tracking for dataspace contract execution."""

    __tablename__ = "dataspace_transfers"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    connector_id: Mapped[UUID] = mapped_column(
        ForeignKey("dataspace_connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    negotiation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dataspace_negotiations.id", ondelete="SET NULL"),
    )
    transfer_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Runtime transfer process ID (e.g., EDC @id)",
    )
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    data_destination: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
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
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_dataspace_transfers_idempotency",
        ),
        Index("ix_dataspace_transfers_connector", "connector_id"),
        Index("ix_dataspace_transfers_external_id", "transfer_id"),
    )


class DataspaceConformanceRun(TenantScopedMixin, Base):
    """Stored conformance run metadata and outcomes for auditability."""

    __tablename__ = "dataspace_conformance_runs"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    connector_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dataspace_connectors.id", ondelete="SET NULL"),
    )
    run_type: Mapped[str] = mapped_column(String(64), nullable=False, default="dsp-tck")
    status: Mapped[DataspaceRunStatus] = mapped_column(
        Enum(DataspaceRunStatus, values_callable=lambda e: [m.value for m in e]),
        default=DataspaceRunStatus.QUEUED,
        nullable=False,
    )
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    artifact_url: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
        Index("ix_dataspace_conformance_runs_tenant_created", "tenant_id", "created_at"),
        Index("ix_dataspace_conformance_runs_status", "status"),
    )


class ResourceShare(TenantScopedMixin, Base):
    """Explicit user-level sharing grants for tenant resources."""

    __tablename__ = "resource_shares"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(nullable=False)
    user_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    permission: Mapped[str] = mapped_column(String(32), nullable=False, default="read")
    granted_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "resource_type",
            "resource_id",
            "user_subject",
            name="uq_resource_shares_target_user",
        ),
        Index("ix_resource_shares_lookup", "tenant_id", "resource_type", "resource_id"),
        Index("ix_resource_shares_user", "tenant_id", "user_subject"),
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
    event_hash: Mapped[str | None] = mapped_column(String(64), comment="SHA-256 hash")
    prev_event_hash: Mapped[str | None] = mapped_column(String(64), comment="Previous event hash")
    chain_sequence: Mapped[int | None] = mapped_column(
        Integer, comment="Monotonic sequence per tenant"
    )
    hash_algorithm: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="sha-256",
        comment="Hash algorithm identifier for event_hash",
    )
    hash_canonicalization: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="rfc8785",
        comment="Canonicalization method used to hash event payload",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_audit_events_subject", "subject"),
        Index("ix_audit_events_action", "action"),
        Index("ix_audit_events_resource", "resource_type", "resource_id"),
        Index("ix_audit_events_created_at", "created_at"),
        Index("ix_audit_events_tenant_chain", "tenant_id", "chain_sequence"),
    )


# =============================================================================
# Audit Merkle Root Model
# =============================================================================


class AuditMerkleRoot(TenantScopedMixin, Base):
    """
    Merkle root anchor for a batch of audit events.

    Provides cryptographic anchoring of event hash chains via Merkle trees,
    with optional digital signature and RFC 3161 timestamping.
    """

    __tablename__ = "audit_merkle_roots"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    root_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 Merkle root hash",
    )
    event_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of events in this Merkle batch",
    )
    first_sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="First chain_sequence in batch",
    )
    last_sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Last chain_sequence in batch",
    )
    signature: Mapped[str | None] = mapped_column(
        Text,
        comment="Ed25519 signature of root_hash",
    )
    signature_kid: Mapped[str | None] = mapped_column(
        String(255),
        comment="Signing key identifier for signature",
    )
    signature_algorithm: Mapped[str | None] = mapped_column(
        String(64),
        comment="Signature algorithm identifier",
    )
    tsa_token: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        comment="RFC 3161 timestamp authority token",
    )
    timestamp_hash_algorithm: Mapped[str | None] = mapped_column(
        String(32),
        comment="Digest algorithm used when requesting TSA timestamp",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_audit_merkle_roots_tenant", "tenant_id"),
        Index(
            "ix_audit_merkle_roots_sequences",
            "tenant_id",
            "first_sequence",
            "last_sequence",
        ),
    )


# =============================================================================
# Compliance Report Model
# =============================================================================


class ComplianceReportRecord(TenantScopedMixin, Base):
    """
    Persisted ESPR compliance check result.

    Stores the full compliance report JSON alongside summary fields
    for efficient querying and dashboard display.
    """

    __tablename__ = "compliance_reports"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    dpp_id: Mapped[UUID] = mapped_column(
        ForeignKey("dpps.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Product category (battery, textile, electronic, etc.)",
    )
    is_compliant: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    report_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Full compliance report payload",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_compliance_reports_tenant_dpp", "tenant_id", "dpp_id"),
        Index("ix_compliance_reports_category", "category"),
    )


# =============================================================================
# EDC Asset Registration Model
# =============================================================================


class EDCAssetRegistration(TenantScopedMixin, Base):
    """
    Tracks DPP assets registered in the Eclipse Dataspace Connector.

    Records the EDC asset, policy, and contract definition IDs
    created during DPP publication to a dataspace.
    """

    __tablename__ = "edc_asset_registrations"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    dpp_id: Mapped[UUID] = mapped_column(
        ForeignKey("dpps.id", ondelete="CASCADE"),
        nullable=False,
    )
    connector_id: Mapped[UUID] = mapped_column(
        ForeignKey("connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    edc_asset_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Asset ID in EDC catalog",
    )
    edc_policy_id: Mapped[str | None] = mapped_column(
        String(255),
        comment="Policy definition ID in EDC",
    )
    edc_contract_id: Mapped[str | None] = mapped_column(
        String(255),
        comment="Contract definition ID in EDC",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="registered",
        nullable=False,
        comment="Registration status: registered, active, removed",
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
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
        Index("ix_edc_registrations_tenant_dpp", "tenant_id", "dpp_id"),
        Index("ix_edc_registrations_connector", "connector_id"),
        Index("ix_edc_registrations_asset", "edc_asset_id"),
    )


# =============================================================================
# Digital Thread Event Model
# =============================================================================


class ThreadEvent(TenantScopedMixin, Base):
    """
    Immutable product lifecycle event for digital thread traceability.

    Unlike audit events (which track WHO did WHAT for security), thread events
    track WHAT HAPPENED to a PRODUCT across its lifecycle. Insert-only — no updates.
    """

    __tablename__ = "thread_events"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    dpp_id: Mapped[UUID] = mapped_column(
        ForeignKey("dpps.id", ondelete="CASCADE"),
        nullable=False,
    )
    phase: Mapped[LifecyclePhase] = mapped_column(
        Enum(LifecyclePhase, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        comment="Product lifecycle phase",
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Event type: material_sourced, assembled, shipped, installed, serviced, recycled, etc.",
    )
    source: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="System or organization that emitted the event",
    )
    source_event_id: Mapped[str | None] = mapped_column(
        String(255),
        comment="External event correlation ID",
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        comment="Event-specific data",
    )
    parent_event_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("thread_events.id"),
        comment="Causal parent event for event chains",
    )
    created_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_thread_events_tenant_dpp_phase", "tenant_id", "dpp_id", "phase"),
        Index("ix_thread_events_tenant_created", "tenant_id", "created_at"),
        Index("ix_thread_events_dpp_id", "dpp_id"),
        Index("ix_thread_events_parent", "parent_event_id"),
    )


# =============================================================================
# LCA Calculation Model
# =============================================================================


class LCACalculation(TenantScopedMixin, Base):
    """
    Persisted LCA / Product Carbon Footprint calculation result.

    Stores the full computation for reproducibility: input inventory,
    emission factors version, and detailed breakdown report.
    """

    __tablename__ = "lca_calculations"

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
        comment="DPP revision number used for the calculation",
    )
    methodology: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Calculation methodology, e.g. activity-based-gwp",
    )
    scope: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="LCA scope: cradle-to-gate, gate-to-gate, cradle-to-grave",
    )
    total_gwp_kg_co2e: Mapped[float] = mapped_column(
        Double,
        nullable=False,
        comment="Total GWP in kg CO2 equivalent",
    )
    impact_categories: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        comment="Multi-category impact results",
    )
    material_inventory: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        comment="Extracted input data for reproducibility",
    )
    factor_database_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Emission factor database version used",
    )
    report_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        comment="Full detailed report",
    )
    created_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_lca_calculations_tenant_dpp", "tenant_id", "dpp_id"),
        Index("ix_lca_calculations_dpp_revision", "dpp_id", "revision_no"),
    )


# =============================================================================
# EPCIS 2.0 Event Model
# =============================================================================


class EPCISEvent(TenantScopedMixin, Base):
    """
    EPCIS 2.0 supply-chain event linked to a DPP.

    Captures standardised GS1 EPCIS events (commissioning, shipping,
    transformation, etc.) with type-specific data in a JSONB payload.
    Append-only — corrections use error_declaration referencing the
    erroneous event.
    """

    __tablename__ = "epcis_events"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    dpp_id: Mapped[UUID] = mapped_column(
        ForeignKey("dpps.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Unique EPCIS event URI (urn:uuid:...)",
    )
    event_type: Mapped[EPCISEventType] = mapped_column(
        Enum(EPCISEventType, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When the event occurred",
    )
    event_time_zone_offset: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Timezone offset, e.g. +01:00",
    )
    action: Mapped[str | None] = mapped_column(
        String(20),
        comment="ADD, OBSERVE, or DELETE (NULL for TransformationEvent)",
    )
    biz_step: Mapped[str | None] = mapped_column(
        String(100),
        comment="CBV business step short name",
    )
    disposition: Mapped[str | None] = mapped_column(
        String(100),
        comment="CBV disposition short name",
    )
    read_point: Mapped[str | None] = mapped_column(
        String(512),
        comment="Where the event was observed (URI)",
    )
    biz_location: Mapped[str | None] = mapped_column(
        String(512),
        comment="Business location where objects reside after event (URI)",
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        comment="Type-specific data: epcList, parentID, childEPCs, sensor data, etc.",
    )
    error_declaration: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        comment="EPCIS error declaration for event corrections",
    )
    created_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_epcis_events_tenant_dpp_time", "tenant_id", "dpp_id", "event_time"),
        Index("ix_epcis_events_event_id", "event_id", unique=True),
        Index("ix_epcis_events_biz_step", "biz_step"),
        Index("ix_epcis_events_payload", "payload", postgresql_using="gin"),
    )


# =============================================================================
# Webhook Models
# =============================================================================


class WebhookSubscription(TenantScopedMixin, Base):
    """
    Webhook subscription for DPP lifecycle event notifications.

    Tenant admins register URLs to receive signed HTTP POST callbacks
    when lifecycle events occur (DPP created, published, etc.).
    """

    __tablename__ = "webhook_subscriptions"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Webhook delivery URL (HTTPS recommended)",
    )
    events: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        comment="List of event types to subscribe to",
    )
    secret: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="HMAC-SHA256 signing secret",
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
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

    deliveries: Mapped[list["WebhookDeliveryLog"]] = relationship(
        back_populates="subscription",
        cascade="all, delete-orphan",
        order_by="WebhookDeliveryLog.created_at.desc()",
    )

    __table_args__ = (
        Index("ix_webhook_subscriptions_tenant", "tenant_id"),
        Index("ix_webhook_subscriptions_active", "active"),
        Index("ix_webhook_subscriptions_events", "events", postgresql_using="gin"),
    )


class WebhookDeliveryLog(Base):
    """
    Log of individual webhook delivery attempts.

    Records HTTP status, response body, and attempt number
    for debugging and monitoring webhook reliability.
    """

    __tablename__ = "webhook_delivery_log"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    subscription_id: Mapped[UUID] = mapped_column(
        ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    http_status: Mapped[int | None] = mapped_column(
        Integer,
        comment="HTTP response status code (NULL if connection failed)",
    )
    response_body: Mapped[str | None] = mapped_column(
        Text,
        comment="Response body (truncated to 1KB)",
    )
    attempt: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    subscription: Mapped["WebhookSubscription"] = relationship(back_populates="deliveries")

    __table_args__ = (
        Index("ix_webhook_delivery_log_subscription", "subscription_id"),
        Index("ix_webhook_delivery_log_created", "created_at"),
    )


class EPCISNamedQuery(TenantScopedMixin, Base):
    """Saved EPCIS query definition for reuse (named query).

    Each named query stores a set of ``EPCISQueryParams`` that can be
    executed on demand. Names are unique within a tenant.
    """

    __tablename__ = "epcis_named_queries"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_epcis_named_queries_tenant_name"),
    )


# =============================================================================
# GS1 Digital Link Resolver Model
# =============================================================================


class ResolverLink(TenantScopedMixin, Base):
    """GS1 Digital Link resolver entry mapping identifiers to DPP endpoints."""

    __tablename__ = "resolver_links"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    identifier: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="GS1 identifier stem, e.g. 01/{gtin}/21/{serial}",
    )
    link_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="GS1 link relation type, e.g. gs1:hasDigitalProductPassport",
    )
    href: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Target URL the link resolves to",
    )
    media_type: Mapped[str] = mapped_column(
        String(100),
        default="application/json",
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        default="",
        nullable=False,
    )
    hreflang: Mapped[str] = mapped_column(
        String(20),
        default="en",
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Link priority (higher = preferred)",
    )
    dpp_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dpps.id", ondelete="SET NULL"),
        comment="Associated DPP (optional)",
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    managed_by_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True when this link is managed by platform workflows",
    )
    source_data_carrier_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("data_carriers.id", ondelete="SET NULL"),
        comment="Owning data carrier when managed_by_system=true",
    )
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
        UniqueConstraint(
            "tenant_id",
            "identifier",
            "link_type",
            name="uq_resolver_links_tenant_identifier_type",
        ),
        Index("ix_resolver_links_tenant", "tenant_id"),
        Index("ix_resolver_links_identifier", "identifier"),
        Index("ix_resolver_links_dpp_id", "dpp_id"),
        Index("ix_resolver_links_link_type", "link_type"),
        Index("ix_resolver_links_active", "active"),
        Index("ix_resolver_links_source_data_carrier_id", "source_data_carrier_id"),
    )


# =============================================================================
# Identifier Governance Models (CEN prEN 18219)
# =============================================================================


class EconomicOperator(TenantScopedMixin, Base):
    """Lean tenant-scoped economic operator entity."""

    __tablename__ = "economic_operators"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
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
        Index("ix_economic_operators_tenant_name", "tenant_id", "legal_name"),
        Index("ix_economic_operators_country", "country"),
    )


class Facility(TenantScopedMixin, Base):
    """Lean tenant-scoped facility entity linked to an operator."""

    __tablename__ = "facilities"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("economic_operators.id", ondelete="CASCADE"),
        nullable=False,
    )
    facility_name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
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
        Index("ix_facilities_operator", "operator_id"),
        Index("ix_facilities_tenant_name", "tenant_id", "facility_name"),
    )


class IdentifierScheme(Base):
    """Catalog of supported identifier schemes and canonicalization rules."""

    __tablename__ = "identifier_schemes"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    entity_type: Mapped[IdentifierEntityType] = mapped_column(
        Enum(IdentifierEntityType, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    issuance_model: Mapped[IdentifierIssuanceModel] = mapped_column(
        Enum(IdentifierIssuanceModel, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=IdentifierIssuanceModel.SELF_ISSUED,
    )
    canonicalization_rules: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    validation_rules: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    openness_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
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

    __table_args__ = (
        Index("ix_identifier_schemes_entity_type", "entity_type"),
        Index("ix_identifier_schemes_issuance_model", "issuance_model"),
    )


class ExternalIdentifier(TenantScopedMixin, Base):
    """Canonicalized identifier registry used across DPP, operators, and facilities."""

    __tablename__ = "external_identifiers"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    entity_type: Mapped[IdentifierEntityType] = mapped_column(
        Enum(IdentifierEntityType, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    scheme_code: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("identifier_schemes.code", ondelete="RESTRICT"),
        nullable=False,
    )
    value_raw: Mapped[str] = mapped_column(Text, nullable=False)
    value_canonical: Mapped[str] = mapped_column(Text, nullable=False)
    granularity: Mapped[DataCarrierIdentityLevel | None] = mapped_column(
        Enum(DataCarrierIdentityLevel, values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    status: Mapped[ExternalIdentifierStatus] = mapped_column(
        Enum(ExternalIdentifierStatus, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ExternalIdentifierStatus.ACTIVE,
    )
    replaced_by_identifier_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("external_identifiers.id", ondelete="SET NULL"),
        nullable=True,
    )
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deprecates_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
        UniqueConstraint(
            "scheme_code", "value_canonical", name="uq_external_identifiers_scheme_value"
        ),
        Index("ix_external_identifiers_entity_type", "entity_type"),
        Index("ix_external_identifiers_status", "status"),
        Index(
            "ix_external_identifiers_tenant_scheme_canonical",
            "tenant_id",
            "scheme_code",
            "value_canonical",
        ),
        Index("ix_external_identifiers_tenant_value_raw", "tenant_id", "value_raw"),
    )


class DPPIdentifier(TenantScopedMixin, Base):
    """Link table between DPPs and canonical identifiers."""

    __tablename__ = "dpp_identifiers"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    dpp_id: Mapped[UUID] = mapped_column(
        ForeignKey("dpps.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_identifier_id: Mapped[UUID] = mapped_column(
        ForeignKey("external_identifiers.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("dpp_id", "external_identifier_id", name="uq_dpp_identifier_link"),
        Index("ix_dpp_identifiers_dpp", "dpp_id"),
        Index("ix_dpp_identifiers_external_identifier", "external_identifier_id"),
    )


class OperatorIdentifier(TenantScopedMixin, Base):
    """Link table between operators and canonical identifiers."""

    __tablename__ = "operator_identifiers"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("economic_operators.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_identifier_id: Mapped[UUID] = mapped_column(
        ForeignKey("external_identifiers.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "operator_id", "external_identifier_id", name="uq_operator_identifier_link"
        ),
        Index("ix_operator_identifiers_operator", "operator_id"),
        Index("ix_operator_identifiers_external_identifier", "external_identifier_id"),
    )


class FacilityIdentifier(TenantScopedMixin, Base):
    """Link table between facilities and canonical identifiers."""

    __tablename__ = "facility_identifiers"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    facility_id: Mapped[UUID] = mapped_column(
        ForeignKey("facilities.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_identifier_id: Mapped[UUID] = mapped_column(
        ForeignKey("external_identifiers.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "facility_id", "external_identifier_id", name="uq_facility_identifier_link"
        ),
        Index("ix_facility_identifiers_facility", "facility_id"),
        Index("ix_facility_identifiers_external_identifier", "external_identifier_id"),
    )


# =============================================================================
# Data Carrier Models
# =============================================================================


class DataCarrier(TenantScopedMixin, Base):
    """Lifecycle-managed data carrier record for DPP resolution and rendering."""

    __tablename__ = "data_carriers"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    dpp_id: Mapped[UUID] = mapped_column(
        ForeignKey("dpps.id", ondelete="CASCADE"),
        nullable=False,
    )
    identity_level: Mapped[DataCarrierIdentityLevel] = mapped_column(
        Enum(DataCarrierIdentityLevel, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=DataCarrierIdentityLevel.ITEM,
    )
    identifier_scheme: Mapped[DataCarrierIdentifierScheme] = mapped_column(
        Enum(DataCarrierIdentifierScheme, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=DataCarrierIdentifierScheme.GS1_GTIN,
    )
    carrier_type: Mapped[DataCarrierType] = mapped_column(
        Enum(DataCarrierType, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=DataCarrierType.QR,
    )
    resolver_strategy: Mapped[DataCarrierResolverStrategy] = mapped_column(
        Enum(DataCarrierResolverStrategy, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=DataCarrierResolverStrategy.DYNAMIC_LINKSET,
    )
    status: Mapped[DataCarrierStatus] = mapped_column(
        Enum(DataCarrierStatus, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=DataCarrierStatus.ACTIVE,
    )
    identifier_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Canonical identifier key used for uniqueness and resolver sync",
    )
    identifier_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Identifier components such as gtin, serial, batch, manufacturer part id",
    )
    external_identifier_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("external_identifiers.id", ondelete="SET NULL"),
        nullable=True,
    )
    encoded_uri: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="URI encoded in the carrier",
    )
    payload_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="SHA-256 hash of encoded payload for physical/digital binding evidence",
    )
    layout_profile: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Rendering profile metadata",
    )
    placement_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Placement metadata for product/packaging/docs",
    )
    pre_sale_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    is_gtin_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    replaced_by_carrier_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("data_carriers.id", ondelete="SET NULL"),
    )
    withdrawn_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
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
        Index("ix_data_carriers_dpp_id", "dpp_id"),
        Index("ix_data_carriers_status", "status"),
        Index("ix_data_carriers_identifier_scheme", "identifier_scheme"),
        Index("ix_data_carriers_identifier_key", "identifier_key"),
        Index("ix_data_carriers_external_identifier_id", "external_identifier_id"),
        Index(
            "uq_data_carriers_tenant_identifier_active_like",
            "tenant_id",
            "identifier_key",
            unique=True,
            postgresql_where=text("status IN ('active','deprecated')"),
        ),
    )


class DataCarrierQualityCheck(TenantScopedMixin, Base):
    """Recorded quality verification results for data carriers."""

    __tablename__ = "data_carrier_quality_checks"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    carrier_id: Mapped[UUID] = mapped_column(
        ForeignKey("data_carriers.id", ondelete="CASCADE"),
        nullable=False,
    )
    check_type: Mapped[str] = mapped_column(String(64), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    results: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    performed_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_data_carrier_quality_checks_carrier_id", "carrier_id"),
        Index("ix_data_carrier_quality_checks_check_type", "check_type"),
        Index("ix_data_carrier_quality_checks_performed_at", "performed_at"),
    )


class DataCarrierArtifact(TenantScopedMixin, Base):
    """Stored artifact metadata generated from a data carrier."""

    __tablename__ = "data_carrier_artifacts"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    carrier_id: Mapped[UUID] = mapped_column(
        ForeignKey("data_carriers.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_type: Mapped[DataCarrierArtifactType] = mapped_column(
        Enum(DataCarrierArtifactType, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_data_carrier_artifacts_carrier_id", "carrier_id"),
        Index("ix_data_carrier_artifacts_artifact_type", "artifact_type"),
    )


# =============================================================================
# AAS Registry & Discovery Models
# =============================================================================


class ShellDescriptorRecord(TenantScopedMixin, Base):
    """Built-in AAS registry shell descriptor storage (IDTA-01002-3-1)."""

    __tablename__ = "shell_descriptors"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    aas_id: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="AAS identifier",
    )
    id_short: Mapped[str] = mapped_column(
        String(255),
        default="",
        nullable=False,
    )
    global_asset_id: Mapped[str] = mapped_column(
        String(1024),
        default="",
        nullable=False,
    )
    specific_asset_ids: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        comment="Specific asset ID entries (name/value pairs)",
    )
    submodel_descriptors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        comment="Submodel descriptor objects",
    )
    dpp_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dpps.id", ondelete="SET NULL"),
        comment="Associated DPP (optional)",
    )
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
        UniqueConstraint("tenant_id", "aas_id", name="uq_shell_descriptors_tenant_aas_id"),
        # tenant_id index is auto-created by TenantScopedMixin (index=True)
        Index(
            "ix_shell_descriptors_specific_asset_ids",
            "specific_asset_ids",
            postgresql_using="gin",
        ),
        Index("ix_shell_descriptors_dpp_id", "dpp_id"),
    )


class AssetDiscoveryMapping(TenantScopedMixin, Base):
    """Asset ID to AAS ID discovery mapping."""

    __tablename__ = "asset_discovery_mappings"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    asset_id_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Asset identifier key (e.g., globalAssetId, manufacturerPartId)",
    )
    asset_id_value: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="Asset identifier value",
    )
    aas_id: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="AAS ID that this asset ID maps to",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "asset_id_key",
            "asset_id_value",
            "aas_id",
            name="uq_asset_discovery_tenant_key_value_aas",
        ),
        Index(
            "ix_asset_discovery_tenant_key_value",
            "tenant_id",
            "asset_id_key",
            "asset_id_value",
        ),
    )


# =============================================================================
# Verifiable Credentials
# =============================================================================


class IssuedCredential(TenantScopedMixin, Base):
    """W3C Verifiable Credential issued for a published DPP."""

    __tablename__ = "issued_credentials"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    dpp_id: Mapped[UUID] = mapped_column(
        ForeignKey("dpps.id", ondelete="CASCADE"),
        nullable=False,
        comment="DPP this credential was issued for",
    )
    credential_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Full W3C Verifiable Credential document",
    )
    issuer_did: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="DID of the credential issuer (did:web:...)",
    )
    subject_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Credential subject identifier (urn:uuid:{dpp_id})",
    )
    issuance_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    expiration_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked: Mapped[bool] = mapped_column(
        Boolean,
        server_default="false",
        nullable=False,
    )
    created_by_subject: Mapped[str] = mapped_column(
        String(255),
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

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "dpp_id",
            name="uq_issued_credentials_tenant_dpp",
        ),
    )


# =============================================================================
# Role Upgrade Requests
# =============================================================================


class RoleUpgradeRequest(TenantScopedMixin, Base):
    """User request to upgrade their tenant role (e.g. viewer → publisher)."""

    __tablename__ = "role_upgrade_requests"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    user_subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="OIDC subject of the requesting user",
    )
    requested_role: Mapped[TenantRole] = mapped_column(
        Enum(TenantRole, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        comment="Role being requested",
    )
    status: Mapped[RoleRequestStatus] = mapped_column(
        Enum(RoleRequestStatus, values_callable=lambda e: [m.value for m in e]),
        default=RoleRequestStatus.PENDING,
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        comment="User-provided reason for the request",
    )
    reviewed_by: Mapped[str | None] = mapped_column(
        String(255),
        comment="OIDC subject of the reviewing admin",
    )
    review_note: Mapped[str | None] = mapped_column(
        Text,
        comment="Admin note on the review decision",
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
        Index("ix_role_upgrade_requests_tenant_user", "tenant_id", "user_subject"),
        Index("ix_role_upgrade_requests_status", "status"),
    )


# =============================================================================
# Public Regulatory Timeline
# =============================================================================


class RegulatoryTimelineSnapshot(Base):
    """Cached snapshot of verified public regulatory and standards milestones."""

    __tablename__ = "regulatory_timeline_snapshots"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    events_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Normalized verified timeline event payload",
    )
    digest_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 digest of canonical timeline payload",
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp of latest successful source verification refresh",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Freshness TTL boundary used for stale/fresh status",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (Index("ix_regulatory_timeline_snapshot_fetched_at", "fetched_at"),)


# =============================================================================
# Public CIRPASS Lab
# =============================================================================


class CirpassStorySnapshot(Base):
    """Cached snapshot of latest CIRPASS user stories feed."""

    __tablename__ = "cirpass_story_snapshots"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Parsed story release version (e.g. V3.1)",
    )
    release_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Release date from source metadata",
    )
    source_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Official CIRPASS source page URL",
    )
    zenodo_record_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Resolved Zenodo record URL used for extraction",
    )
    zenodo_record_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Zenodo record id when available",
    )
    stories_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Normalized level/story payload used by the public simulator",
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp of successful source extraction",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("version", "zenodo_record_url", name="uq_cirpass_snapshot_version_record"),
        Index("ix_cirpass_snapshot_fetched_at", "fetched_at"),
    )


class CirpassLeaderboardEntry(Base):
    """Public pseudonymous leaderboard entry for CIRPASS lab runs."""

    __tablename__ = "cirpass_leaderboard_entries"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    sid: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Session identifier from signed browser token",
    )
    ip_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of request client IP",
    )
    nickname: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Public display nickname",
    )
    score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Game score (higher is better)",
    )
    completion_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Completion time in seconds (lower wins tie-break)",
    )
    version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="CIRPASS story version played",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("sid", "version", name="uq_cirpass_leaderboard_sid_version"),
        CheckConstraint("score >= 0", name="ck_cirpass_leaderboard_score_non_negative"),
        CheckConstraint(
            "completion_seconds >= 0",
            name="ck_cirpass_leaderboard_completion_non_negative",
        ),
        Index(
            "ix_cirpass_leaderboard_rank",
            "version",
            "score",
            "completion_seconds",
            "created_at",
        ),
        Index("ix_cirpass_leaderboard_sid_updated", "sid", "updated_at"),
        Index("ix_cirpass_leaderboard_ip_updated", "ip_hash", "updated_at"),
    )


class CirpassLabEvent(Base):
    """Anonymized telemetry events emitted by the CIRPASS lab runner."""

    __tablename__ = "cirpass_lab_events"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    sid_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="HMAC hash derived from signed session sid (no raw sid stored)",
    )
    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Telemetry event type (step_view, step_submit, hint, etc.)",
    )
    story_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Scenario story identifier",
    )
    step_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Scenario step identifier",
    )
    mode: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="Execution mode (mock/live)",
    )
    variant: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Scenario variant (happy/unauthorized/not_found)",
    )
    result: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="Outcome (success/error/info)",
    )
    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Optional client-observed latency in milliseconds",
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Sanitized telemetry metadata without PII",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0", name="ck_cirpass_lab_event_latency"
        ),
        Index("ix_cirpass_lab_events_sid_created", "sid_hash", "created_at"),
        Index("ix_cirpass_lab_events_story_step", "story_id", "step_id", "created_at"),
    )


# =============================================================================
# OPC UA Ingestion Pipeline
# =============================================================================


class OPCUASource(TenantScopedMixin, Base):
    """
    OPC UA server source configuration.

    Stores connection details for an OPC UA endpoint.
    Password is encrypted at rest via ConnectorConfigEncryptor.
    """

    __tablename__ = "opcua_sources"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    endpoint_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="OPC UA endpoint URL, e.g. opc.tcp://host:4840",
    )
    security_policy: Mapped[str | None] = mapped_column(
        String(100),
        comment="e.g. Basic256Sha256",
    )
    security_mode: Mapped[str | None] = mapped_column(
        String(50),
        comment="e.g. SignAndEncrypt",
    )
    auth_type: Mapped[OPCUAAuthType] = mapped_column(
        Enum(OPCUAAuthType, values_callable=lambda e: [m.value for m in e]),
        default=OPCUAAuthType.ANONYMOUS,
        nullable=False,
    )
    username: Mapped[str | None] = mapped_column(String(255))
    password_encrypted: Mapped[str | None] = mapped_column(
        Text,
        comment="AES-256-GCM encrypted password (enc:v1: prefix)",
    )
    client_cert_ref: Mapped[str | None] = mapped_column(
        Text,
        comment="MinIO object key for client certificate",
    )
    client_key_ref: Mapped[str | None] = mapped_column(
        Text,
        comment="MinIO object key for client private key",
    )
    server_cert_pinned_sha256: Mapped[str | None] = mapped_column(
        String(64),
        comment="Optional SHA-256 pin of server certificate",
    )
    connection_status: Mapped[OPCUAConnectionStatus] = mapped_column(
        Enum(OPCUAConnectionStatus, values_callable=lambda e: [m.value for m in e]),
        default=OPCUAConnectionStatus.DISABLED,
        nullable=False,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="OIDC subject of creator",
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

    nodesets: Mapped[list["OPCUANodeSet"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )
    mappings: Mapped[list["OPCUAMapping"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_opcua_sources_status", "connection_status"),
        Index("ix_opcua_sources_endpoint", "endpoint_url"),
    )


class OPCUANodeSet(TenantScopedMixin, Base):
    """
    Uploaded OPC UA NodeSet2.xml companion spec.

    Stores parsed metadata and a reference to the XML file in object storage.
    The parsed_node_graph JSONB column holds the full node hierarchy for
    search and mapping assistance.
    """

    __tablename__ = "opcua_nodesets"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    source_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("opcua_sources.id", ondelete="SET NULL"),
        comment="Optional link to a source (standalone uploads allowed)",
    )
    namespace_uri: Mapped[str] = mapped_column(Text, nullable=False)
    nodeset_version: Mapped[str | None] = mapped_column(String(100))
    publication_date: Mapped[date | None] = mapped_column(Date)
    companion_spec_name: Mapped[str | None] = mapped_column(String(255))
    companion_spec_version: Mapped[str | None] = mapped_column(String(100))
    nodeset_file_ref: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="MinIO object key for NodeSet2.xml",
    )
    companion_spec_file_ref: Mapped[str | None] = mapped_column(
        Text,
        comment="MinIO object key for companion spec PDF",
    )
    hash_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 of the uploaded NodeSet XML",
    )
    parsed_node_graph: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Full parsed node hierarchy for search and mapping",
    )
    parsed_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Counts: objects, variables, datatypes, engineering units",
    )
    created_by: Mapped[str] = mapped_column(
        String(255),
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

    source: Mapped["OPCUASource | None"] = relationship(back_populates="nodesets")

    __table_args__ = (
        Index("ix_opcua_nodesets_namespace", "tenant_id", "namespace_uri"),
        Index(
            "ix_opcua_nodesets_node_graph",
            "parsed_node_graph",
            postgresql_using="gin",
        ),
    )


class OPCUAMapping(TenantScopedMixin, Base):
    """
    Mapping from an OPC UA node to an AAS submodel path or EPCIS event.

    Dual-purpose: AAS_PATCH applies value changes to DPP revisions,
    EPCIS_EVENT emits traceability events on trigger conditions.
    """

    __tablename__ = "opcua_mappings"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("opcua_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    nodeset_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("opcua_nodesets.id", ondelete="SET NULL"),
        comment="Optional link for validation context",
    )
    mapping_type: Mapped[OPCUAMappingType] = mapped_column(
        Enum(OPCUAMappingType, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    opcua_node_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="OPC UA NodeId, e.g. ns=4;s=Temperature",
    )
    opcua_browse_path: Mapped[str | None] = mapped_column(
        Text,
        comment="Human-readable browse path for display",
    )
    opcua_datatype: Mapped[str | None] = mapped_column(String(100))
    sampling_interval_ms: Mapped[int | None] = mapped_column(
        Integer,
        comment="Override default sampling interval (ms)",
    )
    # DPP binding
    dpp_binding_mode: Mapped[DPPBindingMode] = mapped_column(
        Enum(DPPBindingMode, values_callable=lambda e: [m.value for m in e]),
        default=DPPBindingMode.BY_DPP_ID,
        nullable=False,
    )
    dpp_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dpps.id", ondelete="SET NULL"),
        comment="Target DPP when binding_mode=BY_DPP_ID",
    )
    asset_id_query: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        comment="Query for BY_ASSET_IDS mode, e.g. {gtin, serialNumber}",
    )
    # AAS target
    target_template_key: Mapped[str | None] = mapped_column(String(100))
    target_submodel_id: Mapped[str | None] = mapped_column(Text)
    target_aas_path: Mapped[str | None] = mapped_column(
        Text,
        comment="Canonical patch path within AAS submodel",
    )
    patch_op: Mapped[str | None] = mapped_column(
        String(50),
        comment="Canonical op: set_value, set_multilang, add_list_item, etc.",
    )
    value_transform_expr: Mapped[str | None] = mapped_column(
        Text,
        comment="Transform DSL expression, e.g. scale:0.001|round:2",
    )
    unit_hint: Mapped[str | None] = mapped_column(String(50))
    # SAMM metadata
    samm_aspect_urn: Mapped[str | None] = mapped_column(
        Text,
        comment="Catena-X SAMM aspect model URN",
    )
    samm_property: Mapped[str | None] = mapped_column(String(255))
    samm_version: Mapped[str | None] = mapped_column(String(50))
    # EPCIS metadata (used when mapping_type=EPCIS_EVENT)
    epcis_event_type: Mapped[str | None] = mapped_column(String(50))
    epcis_biz_step: Mapped[str | None] = mapped_column(Text)
    epcis_disposition: Mapped[str | None] = mapped_column(Text)
    epcis_action: Mapped[str | None] = mapped_column(String(20))
    epcis_read_point: Mapped[str | None] = mapped_column(Text)
    epcis_biz_location: Mapped[str | None] = mapped_column(Text)
    epcis_source_event_id_template: Mapped[str | None] = mapped_column(
        Text,
        comment="Template for idempotent event ID generation",
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    source: Mapped["OPCUASource"] = relationship(back_populates="mappings")

    __table_args__ = (
        Index("ix_opcua_mappings_source", "source_id"),
        Index("ix_opcua_mappings_dpp", "dpp_id"),
        Index("ix_opcua_mappings_type", "mapping_type"),
    )


class OPCUAJob(TenantScopedMixin, Base):
    """
    Worker state tracking for an active OPC UA mapping subscription.

    The agent uses this to track which mappings are subscribed and the
    last flushed value/timestamp per mapping.
    """

    __tablename__ = "opcua_jobs"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("opcua_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    mapping_id: Mapped[UUID] = mapped_column(
        ForeignKey("opcua_mappings.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="idle",
        nullable=False,
        comment="idle, subscribed, paused, error",
    )
    last_value_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        comment="Last received OPC UA value + quality + timestamp",
    )
    last_flush_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
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
        UniqueConstraint("mapping_id", name="uq_opcua_jobs_mapping"),
        Index("ix_opcua_jobs_source", "source_id"),
    )


class OPCUADeadLetter(TenantScopedMixin, Base):
    """
    Dead-letter record for failed OPC UA → DPP mapping operations.

    Tracks persistent failures so operators can diagnose and fix mappings.
    Count is incremented on repeated failures for the same mapping.
    """

    __tablename__ = "opcua_deadletters"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    mapping_id: Mapped[UUID] = mapped_column(
        ForeignKey("opcua_mappings.id", ondelete="CASCADE"),
        nullable=False,
    )
    value_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        comment="OPC UA value that failed to apply (may be redacted)",
    )
    error: Mapped[str] = mapped_column(Text, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_opcua_deadletters_mapping", "mapping_id"),
        Index("ix_opcua_deadletters_last_seen", "last_seen_at"),
    )


class OPCUAInventorySnapshot(TenantScopedMixin, Base):
    """
    Cached snapshot of an OPC UA server's browse results.

    Stores NamespaceArray, server info, and discovered nodes for
    offline reference and mapping assistance.
    """

    __tablename__ = "opcua_inventory_snapshots"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("opcua_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Server browse results: namespaces, capabilities, node summary",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (Index("ix_opcua_snapshots_source", "source_id"),)


class DataspacePublicationJob(TenantScopedMixin, Base):
    """
    Tracks publication of a DPP to dataspace components (DTR, EDC).

    State machine: queued → running → succeeded | failed.
    Retryable on failure.
    """

    __tablename__ = "dataspace_publication_jobs"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v7(),
    )
    dpp_id: Mapped[UUID] = mapped_column(
        ForeignKey("dpps.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[DataspacePublicationStatus] = mapped_column(
        Enum(
            DataspacePublicationStatus,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=DataspacePublicationStatus.QUEUED,
        nullable=False,
    )
    target: Mapped[str] = mapped_column(
        String(50),
        default="catena-x",
        nullable=False,
        comment="Target ecosystem, e.g. catena-x",
    )
    artifact_refs: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        comment="Published artifact references (DTR IDs, EDC asset IDs, etc.)",
    )
    error: Mapped[str | None] = mapped_column(Text)
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
        Index("ix_ds_pub_jobs_dpp", "dpp_id"),
        Index("ix_ds_pub_jobs_status", "status"),
    )
