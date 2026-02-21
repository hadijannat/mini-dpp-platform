"""Service layer for lifecycle-managed data carriers."""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote, urlparse
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import (
    DPP,
    DataCarrier,
    DataCarrierArtifact,
    DataCarrierArtifactType,
    DataCarrierQualityCheck,
    DPPStatus,
    ExternalIdentifierStatus,
    IdentifierEntityType,
    ResolverLink,
)
from app.db.models import (
    DataCarrierIdentifierScheme as DataCarrierIdentifierSchemeDB,
)
from app.db.models import (
    DataCarrierIdentityLevel as DataCarrierIdentityLevelDB,
)
from app.db.models import (
    DataCarrierResolverStrategy as DataCarrierResolverStrategyDB,
)
from app.db.models import (
    DataCarrierStatus as DataCarrierStatusDB,
)
from app.db.models import (
    DataCarrierType as DataCarrierTypeDB,
)
from app.modules.data_carriers.schemas import (
    DataCarrierCreateRequest,
    DataCarrierDeprecateRequest,
    DataCarrierIdentifierData,
    DataCarrierIdentifierScheme,
    DataCarrierIdentityLevel,
    DataCarrierPreSalePackResponse,
    DataCarrierQACheckResult,
    DataCarrierQAResponse,
    DataCarrierQualityCheckCreateRequest,
    DataCarrierQualityCheckResponse,
    DataCarrierRegistryExportItem,
    DataCarrierRegistryExportResponse,
    DataCarrierReissueRequest,
    DataCarrierRenderRequest,
    DataCarrierResolverStrategy,
    DataCarrierStatus,
    DataCarrierType,
    DataCarrierUpdateRequest,
    DataCarrierValidationRequest,
    DataCarrierValidationResponse,
    DataCarrierWithdrawRequest,
)
from app.modules.qr.service import QRCodeService
from app.modules.resolver.schemas import LinkType
from app.standards.cen_pren.data_carriers_18220.renderers import (
    DataMatrixRenderer,
    NFCRenderer,
    QRRenderer,
)
from app.standards.cen_pren.identifiers_18219 import IdentifierGovernanceError, IdentifierService

logger = get_logger(__name__)


class DataCarrierError(ValueError):
    """Raised for invalid carrier operations."""


class DataCarrierUnsupportedError(DataCarrierError):
    """Raised when carrier rendering is unsupported in the runtime."""


@dataclass
class RenderedCarrier:
    """Binary render result for a carrier."""

    payload: bytes
    media_type: str
    extension: str
    artifact: DataCarrierArtifact | None


class DataCarrierService:
    """Business logic for data carrier lifecycle and resolver synchronization."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
        self._qr = QRCodeService()
        self._identifier_service = IdentifierService(session)
        self._qr_renderer = QRRenderer()
        self._datamatrix_renderer = DataMatrixRenderer()
        self._nfc_renderer = NFCRenderer()

    async def create_carrier(
        self,
        *,
        tenant_id: UUID,
        tenant_slug: str,
        created_by: str,
        request: DataCarrierCreateRequest,
    ) -> DataCarrier:
        dpp = await self._get_published_dpp(request.dpp_id, tenant_id)
        identifier_key, encoded_uri, normalized_identifier_data, is_gtin_verified = (
            self._build_identifier_representation(
                dpp=dpp,
                tenant_slug=tenant_slug,
                identity_level=request.identity_level,
                identifier_scheme=request.identifier_scheme,
                resolver_strategy=request.resolver_strategy,
                identifier_data=request.identifier_data,
            )
        )

        external_identifier_id = await self._register_external_identifier_for_carrier(
            tenant_id=tenant_id,
            created_by=created_by,
            dpp_id=dpp.id,
            identity_level=request.identity_level,
            identifier_scheme=request.identifier_scheme,
            normalized_identifier_data=normalized_identifier_data,
            encoded_uri=encoded_uri,
        )

        carrier = DataCarrier(
            tenant_id=tenant_id,
            dpp_id=dpp.id,
            identity_level=DataCarrierIdentityLevelDB(request.identity_level.value),
            identifier_scheme=DataCarrierIdentifierSchemeDB(request.identifier_scheme.value),
            carrier_type=DataCarrierTypeDB(request.carrier_type.value),
            resolver_strategy=DataCarrierResolverStrategyDB(request.resolver_strategy.value),
            status=DataCarrierStatusDB.ACTIVE,
            identifier_key=identifier_key,
            identifier_data=normalized_identifier_data,
            external_identifier_id=external_identifier_id,
            encoded_uri=encoded_uri,
            payload_sha256=self._hash_payload(encoded_uri),
            layout_profile=request.layout_profile.model_dump(exclude_none=True),
            placement_metadata=request.placement_metadata.model_dump(exclude_none=True),
            pre_sale_enabled=request.pre_sale_enabled,
            is_gtin_verified=is_gtin_verified,
            created_by_subject=created_by,
        )
        self._session.add(carrier)
        await self._session.flush()

        await self._sync_resolver_links(
            carrier=carrier,
            dpp=dpp,
            tenant_slug=tenant_slug,
            updated_by=created_by,
            withdrawal_url=None,
        )

        return carrier

    async def list_carriers(
        self,
        *,
        tenant_id: UUID,
        dpp_id: UUID | None = None,
        status: DataCarrierStatus | None = None,
        identity_level: DataCarrierIdentityLevel | None = None,
        identifier_scheme: DataCarrierIdentifierScheme | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DataCarrier]:
        stmt: Select[tuple[DataCarrier]] = select(DataCarrier).where(
            DataCarrier.tenant_id == tenant_id
        )
        if dpp_id is not None:
            stmt = stmt.where(DataCarrier.dpp_id == dpp_id)
        if status is not None:
            stmt = stmt.where(DataCarrier.status == DataCarrierStatusDB(status.value))
        if identity_level is not None:
            stmt = stmt.where(
                DataCarrier.identity_level == DataCarrierIdentityLevelDB(identity_level.value)
            )
        if identifier_scheme is not None:
            stmt = stmt.where(
                DataCarrier.identifier_scheme
                == DataCarrierIdentifierSchemeDB(identifier_scheme.value)
            )
        stmt = stmt.order_by(DataCarrier.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_carrier(self, carrier_id: UUID, tenant_id: UUID) -> DataCarrier | None:
        result = await self._session.execute(
            select(DataCarrier).where(
                DataCarrier.id == carrier_id,
                DataCarrier.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_carrier(
        self,
        *,
        carrier_id: UUID,
        tenant_id: UUID,
        tenant_slug: str,
        request: DataCarrierUpdateRequest,
        updated_by: str,
    ) -> DataCarrier:
        carrier = await self.get_carrier(carrier_id, tenant_id)
        if carrier is None:
            raise DataCarrierError("Carrier not found")

        if request.carrier_type is not None:
            carrier.carrier_type = DataCarrierTypeDB(request.carrier_type.value)
        if request.resolver_strategy is not None:
            if (
                carrier.identifier_scheme == DataCarrierIdentifierSchemeDB.GS1_GTIN
                and request.resolver_strategy.value
                != DataCarrierResolverStrategy.DYNAMIC_LINKSET.value
            ):
                raise DataCarrierError("GS1 carriers require resolver_strategy='dynamic_linkset'")
            carrier.resolver_strategy = DataCarrierResolverStrategyDB(
                request.resolver_strategy.value
            )
        if request.layout_profile is not None:
            carrier.layout_profile = request.layout_profile.model_dump(exclude_none=True)
        if request.placement_metadata is not None:
            carrier.placement_metadata = request.placement_metadata.model_dump(exclude_none=True)
        if request.pre_sale_enabled is not None:
            carrier.pre_sale_enabled = request.pre_sale_enabled

        dpp = await self._get_published_dpp(carrier.dpp_id, tenant_id)
        await self._sync_resolver_links(
            carrier=carrier,
            dpp=dpp,
            tenant_slug=tenant_slug,
            updated_by=updated_by,
            withdrawal_url=None,
        )

        await self._session.flush()
        return carrier

    async def deprecate_carrier(
        self,
        *,
        carrier_id: UUID,
        tenant_id: UUID,
        tenant_slug: str,
        request: DataCarrierDeprecateRequest,
        updated_by: str,
    ) -> DataCarrier:
        carrier = await self.get_carrier(carrier_id, tenant_id)
        if carrier is None:
            raise DataCarrierError("Carrier not found")
        if carrier.status == DataCarrierStatusDB.WITHDRAWN:
            raise DataCarrierError("Withdrawn carriers cannot be deprecated")

        if request.replaced_by_carrier_id is not None:
            replacement = await self.get_carrier(request.replaced_by_carrier_id, tenant_id)
            if replacement is None:
                raise DataCarrierError("Replacement carrier not found")
            carrier.replaced_by_carrier_id = replacement.id

        carrier.status = DataCarrierStatusDB.DEPRECATED
        dpp = await self._get_published_dpp(carrier.dpp_id, tenant_id)
        await self._sync_resolver_links(
            carrier=carrier,
            dpp=dpp,
            tenant_slug=tenant_slug,
            updated_by=updated_by,
            withdrawal_url=None,
        )
        await self._session.flush()
        return carrier

    async def withdraw_carrier(
        self,
        *,
        carrier_id: UUID,
        tenant_id: UUID,
        tenant_slug: str,
        request: DataCarrierWithdrawRequest,
        updated_by: str,
    ) -> DataCarrier:
        carrier = await self.get_carrier(carrier_id, tenant_id)
        if carrier is None:
            raise DataCarrierError("Carrier not found")

        carrier.status = DataCarrierStatusDB.WITHDRAWN
        carrier.withdrawn_reason = request.reason

        dpp = await self._get_published_dpp(carrier.dpp_id, tenant_id)
        await self._sync_resolver_links(
            carrier=carrier,
            dpp=dpp,
            tenant_slug=tenant_slug,
            updated_by=updated_by,
            withdrawal_url=(str(request.withdrawal_url) if request.withdrawal_url else None),
        )
        await self._session.flush()
        return carrier

    async def reissue_carrier(
        self,
        *,
        carrier_id: UUID,
        tenant_id: UUID,
        tenant_slug: str,
        request: DataCarrierReissueRequest,
        updated_by: str,
    ) -> DataCarrier:
        old = await self.get_carrier(carrier_id, tenant_id)
        if old is None:
            raise DataCarrierError("Carrier not found")

        # Mark old as withdrawn first to avoid unique-key conflict on identifier_key.
        old.status = DataCarrierStatusDB.WITHDRAWN
        old.withdrawn_reason = "reissued"
        await self._session.flush()

        new_carrier = DataCarrier(
            tenant_id=old.tenant_id,
            dpp_id=old.dpp_id,
            identity_level=old.identity_level,
            identifier_scheme=old.identifier_scheme,
            carrier_type=(
                DataCarrierTypeDB(request.carrier_type.value)
                if request.carrier_type
                else old.carrier_type
            ),
            resolver_strategy=(
                DataCarrierResolverStrategyDB(request.resolver_strategy.value)
                if request.resolver_strategy
                else old.resolver_strategy
            ),
            status=DataCarrierStatusDB.ACTIVE,
            identifier_key=old.identifier_key,
            identifier_data=old.identifier_data,
            external_identifier_id=old.external_identifier_id,
            encoded_uri=old.encoded_uri,
            payload_sha256=old.payload_sha256,
            layout_profile=(
                request.layout_profile.model_dump(exclude_none=True)
                if request.layout_profile
                else old.layout_profile
            ),
            placement_metadata=(
                request.placement_metadata.model_dump(exclude_none=True)
                if request.placement_metadata
                else old.placement_metadata
            ),
            pre_sale_enabled=(
                request.pre_sale_enabled
                if request.pre_sale_enabled is not None
                else old.pre_sale_enabled
            ),
            is_gtin_verified=old.is_gtin_verified,
            created_by_subject=updated_by,
        )
        self._session.add(new_carrier)
        await self._session.flush()

        old.replaced_by_carrier_id = new_carrier.id

        dpp = await self._get_published_dpp(new_carrier.dpp_id, tenant_id)
        await self._sync_resolver_links(
            carrier=old,
            dpp=dpp,
            tenant_slug=tenant_slug,
            updated_by=updated_by,
            withdrawal_url=None,
        )
        await self._sync_resolver_links(
            carrier=new_carrier,
            dpp=dpp,
            tenant_slug=tenant_slug,
            updated_by=updated_by,
            withdrawal_url=None,
        )
        await self._session.flush()

        return new_carrier

    async def render_carrier(
        self,
        *,
        carrier_id: UUID,
        tenant_id: UUID,
        request: DataCarrierRenderRequest,
    ) -> RenderedCarrier:
        carrier = await self.get_carrier(carrier_id, tenant_id)
        if carrier is None:
            raise DataCarrierError("Carrier not found")

        if carrier.status == DataCarrierStatusDB.WITHDRAWN:
            raise DataCarrierError("Withdrawn carriers cannot be rendered")

        layout = carrier.layout_profile or {}
        size = int(layout.get("size", 400))
        foreground = str(layout.get("foreground_color", "#000000"))
        background = str(layout.get("background_color", "#FFFFFF"))
        include_text = bool(layout.get("include_text", True))
        text_label = layout.get("text_label")
        if text_label is not None:
            text_label = str(text_label)
        output = request.output_type.value
        profile = {
            "size": size,
            "foreground_color": foreground,
            "background_color": background,
            "include_text": include_text,
            "text_label": text_label,
            "error_correction": str(layout.get("error_correction", "H")),
            "quiet_zone_modules": int(layout.get("quiet_zone_modules", 4)),
            "nfc_memory_bytes": int(layout.get("nfc_memory_bytes", 512)),
        }

        if carrier.carrier_type == DataCarrierTypeDB.QR:
            payload = self._qr_renderer.render(
                payload=carrier.encoded_uri,
                output_type=output,
                profile=profile,
            )
            media_type = {
                "png": "image/png",
                "svg": "image/svg+xml",
                "pdf": "application/pdf",
            }.get(output, "application/octet-stream")
            extension = output
        elif carrier.carrier_type == DataCarrierTypeDB.DATAMATRIX:
            try:
                payload = self._datamatrix_renderer.render(
                    payload=carrier.encoded_uri,
                    output_type=output,
                    profile=profile,
                )
            except NotImplementedError as exc:
                raise DataCarrierUnsupportedError(str(exc)) from exc
            media_type = "image/png"
            extension = "png"
        elif carrier.carrier_type == DataCarrierTypeDB.NFC:
            payload = self._nfc_renderer.render(
                payload=carrier.encoded_uri,
                output_type=output,
                profile=profile,
            )
            media_type = "application/vnd.ndef"
            extension = "ndef"
        else:
            raise DataCarrierError(f"Unsupported carrier type: {carrier.carrier_type.value}")

        artifact: DataCarrierArtifact | None = None
        if request.persist_artifact:
            if extension not in {item.value for item in DataCarrierArtifactType}:
                raise DataCarrierError("persist_artifact is not supported for this output type")
            digest = hashlib.sha256(payload).hexdigest()
            artifact_type = DataCarrierArtifactType(extension)
            artifact = DataCarrierArtifact(
                tenant_id=tenant_id,
                carrier_id=carrier.id,
                artifact_type=artifact_type,
                storage_uri=(
                    f"inline://data-carriers/{carrier.id}/{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
                    f".{extension}"
                ),
                sha256=digest,
            )
            self._session.add(artifact)
            await self._session.flush()

        return RenderedCarrier(
            payload=payload,
            media_type=media_type,
            extension=extension,
            artifact=artifact,
        )

    async def build_pre_sale_pack(
        self,
        *,
        carrier_id: UUID,
        tenant_id: UUID,
        tenant_slug: str,
    ) -> DataCarrierPreSalePackResponse:
        carrier = await self.get_carrier(carrier_id, tenant_id)
        if carrier is None:
            raise DataCarrierError("Carrier not found")

        consumer_url = self._qr.build_dpp_url(
            str(carrier.dpp_id), tenant_slug=tenant_slug, short_link=False
        )
        widget_html = (
            '<div class="dpp-widget">'
            f'<a href="{consumer_url}" target="_blank" rel="noopener noreferrer">'
            "View Digital Product Passport"
            "</a>"
            "</div>"
        )

        return DataCarrierPreSalePackResponse(
            carrier_id=carrier.id,
            dpp_id=carrier.dpp_id,
            consumer_url=consumer_url,
            encoded_uri=carrier.encoded_uri,
            widget_html=widget_html,
        )

    async def export_registry_payload(
        self,
        *,
        tenant_id: UUID,
    ) -> DataCarrierRegistryExportResponse:
        rows = await self.list_carriers(tenant_id=tenant_id, limit=5000)
        items = [
            DataCarrierRegistryExportItem(
                carrier_id=row.id,
                dpp_id=row.dpp_id,
                identifier_key=row.identifier_key,
                identifier_scheme=row.identifier_scheme.value,
                encoded_uri=row.encoded_uri,
                status=row.status.value,
                created_at=row.created_at,
            )
            for row in rows
        ]
        return DataCarrierRegistryExportResponse(items=items, count=len(items))

    def validate_payload_preflight(
        self,
        *,
        request: DataCarrierValidationRequest,
    ) -> DataCarrierValidationResponse:
        payload_bytes = len(request.payload.encode("utf-8"))
        warnings: list[str] = []
        details: dict[str, object] = {}
        valid = True

        profile = request.layout_profile.model_dump(exclude_none=True)

        try:
            if request.carrier_type == DataCarrierType.QR:
                self._qr_renderer.validate_payload(request.payload, profile)
                details["error_correction"] = profile.get("error_correction", "H")
                details["quiet_zone_modules"] = profile.get("quiet_zone_modules", 4)
            elif request.carrier_type == DataCarrierType.DATAMATRIX:
                if not self._datamatrix_renderer.is_available():
                    valid = False
                    warnings.append(
                        "DataMatrix renderer unavailable in runtime. Install pylibdmtx/libdmtx."
                    )
                    details["runtime_available"] = False
                else:
                    self._datamatrix_renderer.validate_payload(request.payload, profile)
                    details["runtime_available"] = True
            elif request.carrier_type == DataCarrierType.NFC:
                self._nfc_renderer.validate_payload(request.payload, profile)
                details["nfc_memory_bytes"] = profile.get("nfc_memory_bytes", 512)
            else:
                valid = False
                warnings.append(f"Unsupported carrier type: {request.carrier_type.value}")
        except ValueError as exc:
            valid = False
            warnings.append(str(exc))

        return DataCarrierValidationResponse(
            valid=valid,
            carrier_type=request.carrier_type,
            payload_bytes=payload_bytes,
            warnings=warnings,
            details=details,
        )

    async def build_qa_report(self, *, carrier_id: UUID, tenant_id: UUID) -> DataCarrierQAResponse:
        carrier = await self.get_carrier(carrier_id, tenant_id)
        if carrier is None:
            raise DataCarrierError("Carrier not found")

        checks: list[DataCarrierQACheckResult] = []
        checks.append(
            DataCarrierQACheckResult(
                check_type="payload_roundtrip",
                passed=bool(carrier.encoded_uri.strip()),
                severity="error" if not carrier.encoded_uri.strip() else "info",
                message=(
                    "Encoded payload is non-empty"
                    if carrier.encoded_uri.strip()
                    else "Encoded payload is empty"
                ),
            )
        )
        checks.append(
            DataCarrierQACheckResult(
                check_type="status_gate",
                passed=carrier.status != DataCarrierStatusDB.WITHDRAWN,
                severity="warning" if carrier.status == DataCarrierStatusDB.WITHDRAWN else "info",
                message=f"Carrier status is {carrier.status.value}",
                details={"status": carrier.status.value},
            )
        )

        layout = carrier.layout_profile or {}
        if carrier.carrier_type == DataCarrierTypeDB.QR:
            err = str(layout.get("error_correction", "H")).upper()
            quiet = int(layout.get("quiet_zone_modules", 4))
            checks.append(
                DataCarrierQACheckResult(
                    check_type="qr_error_correction",
                    passed=err in {"L", "M", "Q", "H"},
                    severity="error" if err not in {"L", "M", "Q", "H"} else "info",
                    message=f"QR error correction: {err}",
                    details={"error_correction": err},
                )
            )
            checks.append(
                DataCarrierQACheckResult(
                    check_type="qr_quiet_zone",
                    passed=1 <= quiet <= 16,
                    severity="warning" if not (1 <= quiet <= 16) else "info",
                    message=f"QR quiet zone modules: {quiet}",
                    details={"quiet_zone_modules": quiet},
                )
            )
        if carrier.carrier_type == DataCarrierTypeDB.DATAMATRIX:
            available = self._datamatrix_renderer.is_available()
            checks.append(
                DataCarrierQACheckResult(
                    check_type="datamatrix_runtime",
                    passed=available,
                    severity="warning" if not available else "info",
                    message=(
                        "DataMatrix runtime dependency available"
                        if available
                        else "DataMatrix runtime dependency missing"
                    ),
                )
            )
        if carrier.carrier_type == DataCarrierTypeDB.NFC:
            memory = int(layout.get("nfc_memory_bytes", 512))
            required = len(carrier.encoded_uri.encode("utf-8")) + 5
            checks.append(
                DataCarrierQACheckResult(
                    check_type="nfc_capacity",
                    passed=required <= memory,
                    severity="error" if required > memory else "info",
                    message=f"NFC capacity {required}/{memory} bytes",
                    details={"required_bytes": required, "nfc_memory_bytes": memory},
                )
            )

        return DataCarrierQAResponse(carrier_id=carrier.id, checks=checks)

    async def add_quality_check(
        self,
        *,
        carrier_id: UUID,
        tenant_id: UUID,
        created_by: str,
        request: DataCarrierQualityCheckCreateRequest,
    ) -> DataCarrierQualityCheckResponse:
        carrier = await self.get_carrier(carrier_id, tenant_id)
        if carrier is None:
            raise DataCarrierError("Carrier not found")
        row = DataCarrierQualityCheck(
            tenant_id=tenant_id,
            carrier_id=carrier_id,
            check_type=request.check_type,
            passed=request.passed,
            results=request.results,
            performed_by_subject=created_by,
        )
        self._session.add(row)
        await self._session.flush()
        return DataCarrierQualityCheckResponse(
            id=row.id,
            carrier_id=row.carrier_id,
            check_type=row.check_type,
            passed=row.passed,
            results=row.results,
            performed_by_subject=row.performed_by_subject,
            performed_at=row.performed_at,
        )

    @staticmethod
    def registry_payload_to_csv(payload: DataCarrierRegistryExportResponse) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "carrier_id",
                "dpp_id",
                "identifier_key",
                "identifier_scheme",
                "encoded_uri",
                "status",
                "created_at",
            ]
        )
        for item in payload.items:
            writer.writerow(
                [
                    str(item.carrier_id),
                    str(item.dpp_id),
                    item.identifier_key,
                    item.identifier_scheme.value,
                    item.encoded_uri,
                    item.status.value,
                    item.created_at.isoformat(),
                ]
            )
        return output.getvalue()

    async def _get_published_dpp(self, dpp_id: UUID, tenant_id: UUID) -> DPP:
        result = await self._session.execute(
            select(DPP).where(
                DPP.id == dpp_id,
                DPP.tenant_id == tenant_id,
            )
        )
        dpp = result.scalar_one_or_none()
        if dpp is None:
            raise DataCarrierError("DPP not found")
        if dpp.status != DPPStatus.PUBLISHED:
            raise DataCarrierError("Data carriers can only be created for published DPPs")
        return dpp

    @staticmethod
    def _hash_payload(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def _register_external_identifier_for_carrier(
        self,
        *,
        tenant_id: UUID,
        created_by: str,
        dpp_id: UUID,
        identity_level: DataCarrierIdentityLevel,
        identifier_scheme: DataCarrierIdentifierScheme,
        normalized_identifier_data: dict[str, str],
        encoded_uri: str,
    ) -> UUID | None:
        if identifier_scheme == DataCarrierIdentifierScheme.GS1_GTIN:
            value_raw = normalized_identifier_data.get("gtin", "").strip()
            scheme_code = "gs1_gtin"
        elif identifier_scheme == DataCarrierIdentifierScheme.IEC61406:
            value_raw = encoded_uri
            scheme_code = "iec61406"
        else:
            value_raw = normalized_identifier_data.get("direct_url", "").strip() or encoded_uri
            scheme_code = "direct_url"

        if not value_raw:
            return None

        try:
            identifier = await self._identifier_service.reserve_or_register(
                tenant_id=tenant_id,
                created_by=created_by,
                entity_type=IdentifierEntityType.PRODUCT,
                scheme_code=scheme_code,
                value_raw=value_raw,
                granularity=DataCarrierIdentityLevelDB(identity_level.value),
            )
            if identifier.status != ExternalIdentifierStatus.ACTIVE:
                identifier.status = ExternalIdentifierStatus.ACTIVE
            await self._identifier_service.link_identifier_to_dpp(
                tenant_id=tenant_id,
                dpp_id=dpp_id,
                external_identifier_id=identifier.id,
            )
            return identifier.id
        except IdentifierGovernanceError as exc:
            raise DataCarrierError(f"Identifier governance failed: {exc}") from exc

    def _build_identifier_representation(
        self,
        *,
        dpp: DPP,
        tenant_slug: str,
        identity_level: DataCarrierIdentityLevel,
        identifier_scheme: DataCarrierIdentifierScheme,
        resolver_strategy: DataCarrierResolverStrategy,
        identifier_data: DataCarrierIdentifierData,
    ) -> tuple[str, str, dict[str, str], bool]:
        if identifier_scheme == DataCarrierIdentifierScheme.GS1_GTIN:
            if resolver_strategy != DataCarrierResolverStrategy.DYNAMIC_LINKSET:
                raise DataCarrierError("GS1 carriers require resolver_strategy='dynamic_linkset'")
            return self._build_gs1_identifier(
                identity_level=identity_level, identifier_data=identifier_data
            )

        if identifier_scheme == DataCarrierIdentifierScheme.IEC61406:
            return self._build_iec61406_identifier(
                dpp=dpp,
                tenant_slug=tenant_slug,
                identity_level=identity_level,
                identifier_data=identifier_data,
            )

        return self._build_direct_url_identifier(identifier_data)

    def _build_gs1_identifier(
        self,
        *,
        identity_level: DataCarrierIdentityLevel,
        identifier_data: DataCarrierIdentifierData,
    ) -> tuple[str, str, dict[str, str], bool]:
        gtin_raw = "".join(filter(str.isdigit, (identifier_data.gtin or "")))
        if not gtin_raw:
            raise DataCarrierError("GTIN is required for gs1_gtin carriers")
        if not QRCodeService.validate_gtin(gtin_raw):
            raise DataCarrierError("GTIN must include a valid GS1 check digit")

        serial = (identifier_data.serial or "").strip()
        batch = (identifier_data.batch or "").strip()

        if identity_level == DataCarrierIdentityLevel.MODEL:
            key = f"01/{quote(gtin_raw, safe='')}"
        elif identity_level == DataCarrierIdentityLevel.BATCH:
            if not batch:
                raise DataCarrierError("Batch is required for batch-level GS1 carriers")
            key = f"01/{quote(gtin_raw, safe='')}/10/{quote(batch, safe='')}"
        else:
            if not serial:
                raise DataCarrierError("Serial is required for item-level GS1 carriers")
            if batch:
                key = (
                    f"01/{quote(gtin_raw, safe='')}/21/{quote(serial, safe='')}/10/"
                    f"{quote(batch, safe='')}"
                )
            else:
                key = f"01/{quote(gtin_raw, safe='')}/21/{quote(serial, safe='')}"

        resolver_base = self._resolve_resolver_base_url()
        encoded_uri = f"{resolver_base}/{key}"

        data = {"gtin": gtin_raw}
        if serial:
            data["serial"] = serial
        if batch:
            data["batch"] = batch

        return key, encoded_uri, data, True

    def _build_iec61406_identifier(
        self,
        *,
        dpp: DPP,
        tenant_slug: str,
        identity_level: DataCarrierIdentityLevel,
        identifier_data: DataCarrierIdentifierData,
    ) -> tuple[str, str, dict[str, str], bool]:
        manufacturer_part_id = (
            identifier_data.manufacturer_part_id
            or str((dpp.asset_ids or {}).get("manufacturerPartId", ""))
        ).strip()
        serial = (
            identifier_data.serial or str((dpp.asset_ids or {}).get("serialNumber", ""))
        ).strip()
        batch = (identifier_data.batch or "").strip()

        if not manufacturer_part_id:
            raise DataCarrierError("manufacturer_part_id is required for iec61406 carriers")
        if identity_level == DataCarrierIdentityLevel.BATCH and not batch:
            raise DataCarrierError("Batch is required for batch-level IEC 61406 carriers")
        if identity_level == DataCarrierIdentityLevel.ITEM and not serial:
            raise DataCarrierError("Serial is required for item-level IEC 61406 carriers")

        base_url = self._qr.build_dpp_url(str(dpp.id), tenant_slug=tenant_slug, short_link=False)
        query_params = {
            "manufacturerPartId": manufacturer_part_id,
        }
        if serial:
            query_params["serialNumber"] = serial
        if batch:
            query_params["batchId"] = batch

        query_string = "&".join(
            f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in query_params.items()
        )
        encoded_uri = f"{base_url}?{query_string}"

        key = (
            f"iec61406:{identity_level.value}:{quote(manufacturer_part_id, safe='')}"
            f":{quote(serial, safe='')}:{quote(batch, safe='')}"
        )
        data = {"manufacturer_part_id": manufacturer_part_id}
        if serial:
            data["serial"] = serial
        if batch:
            data["batch"] = batch

        return key, encoded_uri, data, False

    def _build_direct_url_identifier(
        self,
        identifier_data: DataCarrierIdentifierData,
    ) -> tuple[str, str, dict[str, str], bool]:
        if identifier_data.direct_url is None:
            raise DataCarrierError("direct_url is required for direct_url carriers")

        url = str(identifier_data.direct_url)
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise DataCarrierError("direct_url must use http or https")

        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
        key = f"direct_url:{digest}"
        return key, url, {"direct_url": url}, False

    def _resolve_resolver_base_url(self) -> str:
        if self._settings.resolver_base_url:
            return self._settings.resolver_base_url.rstrip("/")

        backend_base = "http://localhost:8000"
        return f"{backend_base}{self._settings.api_v1_prefix}/resolve"

    def _resolve_public_api_url(self, *, tenant_slug: str, dpp_id: UUID) -> str:
        resolver_base = self._resolve_resolver_base_url()
        token = f"{self._settings.api_v1_prefix}/resolve"
        backend_base = resolver_base.split(token, 1)[0] if token in resolver_base else resolver_base
        return f"{backend_base}{self._settings.api_v1_prefix}/public/{tenant_slug}/dpps/{dpp_id}"

    def _resolve_withdrawal_notice_url(self, *, tenant_slug: str, carrier_id: UUID) -> str:
        resolver_base = self._resolve_resolver_base_url()
        token = f"{self._settings.api_v1_prefix}/resolve"
        backend_base = resolver_base.split(token, 1)[0] if token in resolver_base else resolver_base
        return (
            f"{backend_base}{self._settings.api_v1_prefix}/public/{tenant_slug}"
            f"/carriers/{carrier_id}/withdrawn"
        )

    def _validate_managed_href(self, href: str) -> None:
        parsed = urlparse(href)
        if parsed.scheme not in ("http", "https"):
            raise DataCarrierError("Managed resolver href must use http/https")
        allowlist = self._settings.carrier_resolver_allowed_hosts_all
        if allowlist and (parsed.hostname or "") not in allowlist:
            raise DataCarrierError("Managed resolver href host is not in allowlist")

    async def _sync_resolver_links(
        self,
        *,
        carrier: DataCarrier,
        dpp: DPP,
        tenant_slug: str,
        updated_by: str,
        withdrawal_url: str | None,
    ) -> None:
        if carrier.identifier_scheme != DataCarrierIdentifierSchemeDB.GS1_GTIN:
            await self._deactivate_managed_links_for_carrier(carrier.id, carrier.tenant_id)
            return

        if carrier.resolver_strategy != DataCarrierResolverStrategyDB.DYNAMIC_LINKSET:
            await self._deactivate_managed_links_for_carrier(carrier.id, carrier.tenant_id)
            return

        dpp_href = self._resolve_public_api_url(tenant_slug=tenant_slug, dpp_id=dpp.id)
        self._validate_managed_href(dpp_href)

        recall_href = (
            withdrawal_url
            if withdrawal_url is not None
            else self._resolve_withdrawal_notice_url(
                tenant_slug=tenant_slug,
                carrier_id=carrier.id,
            )
        )
        self._validate_managed_href(recall_href)

        has_dpp = await self._get_or_create_managed_link(
            tenant_id=carrier.tenant_id,
            carrier_id=carrier.id,
            identifier=carrier.identifier_key,
            link_type=LinkType.HAS_DPP.value,
            created_by=updated_by,
        )
        recall = await self._get_or_create_managed_link(
            tenant_id=carrier.tenant_id,
            carrier_id=carrier.id,
            identifier=carrier.identifier_key,
            link_type=LinkType.RECALL_STATUS.value,
            created_by=updated_by,
        )

        if carrier.status == DataCarrierStatusDB.WITHDRAWN:
            has_dpp.href = dpp_href
            has_dpp.media_type = "application/json"
            has_dpp.title = f"Digital Product Passport for {carrier.identifier_key}"
            has_dpp.priority = 100
            has_dpp.active = False
            has_dpp.dpp_id = dpp.id

            recall.href = recall_href
            recall.media_type = "text/html"
            recall.title = f"Withdrawal status for {carrier.identifier_key}"
            recall.priority = 1000
            recall.active = True
            recall.dpp_id = dpp.id
        else:
            has_dpp.href = dpp_href
            has_dpp.media_type = "application/json"
            has_dpp.title = f"Digital Product Passport for {carrier.identifier_key}"
            has_dpp.priority = 100
            has_dpp.active = True
            has_dpp.dpp_id = dpp.id

            recall.href = recall_href
            recall.media_type = "text/html"
            recall.title = f"Withdrawal status for {carrier.identifier_key}"
            recall.priority = 1000
            recall.active = False
            recall.dpp_id = dpp.id

    async def _deactivate_managed_links_for_carrier(
        self, carrier_id: UUID, tenant_id: UUID
    ) -> None:
        result = await self._session.execute(
            select(ResolverLink).where(
                ResolverLink.tenant_id == tenant_id,
                ResolverLink.source_data_carrier_id == carrier_id,
                ResolverLink.managed_by_system.is_(True),
            )
        )
        links = list(result.scalars().all())
        for link in links:
            link.active = False

    async def _get_or_create_managed_link(
        self,
        *,
        tenant_id: UUID,
        carrier_id: UUID,
        identifier: str,
        link_type: str,
        created_by: str,
    ) -> ResolverLink:
        result = await self._session.execute(
            select(ResolverLink).where(
                ResolverLink.tenant_id == tenant_id,
                ResolverLink.source_data_carrier_id == carrier_id,
                ResolverLink.link_type == link_type,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.identifier = identifier
            existing.managed_by_system = True
            existing.source_data_carrier_id = carrier_id
            return existing

        # Reuse an existing link for the same canonical identifier tuple when present.
        # This avoids creating duplicate rows during reissue/identifier hand-off flows.
        result = await self._session.execute(
            select(ResolverLink).where(
                ResolverLink.tenant_id == tenant_id,
                ResolverLink.identifier == identifier,
                ResolverLink.link_type == link_type,
            )
        )
        existing_for_identifier = result.scalar_one_or_none()
        if existing_for_identifier is not None:
            existing_for_identifier.managed_by_system = True
            existing_for_identifier.source_data_carrier_id = carrier_id
            return existing_for_identifier

        link = ResolverLink(
            tenant_id=tenant_id,
            identifier=identifier,
            link_type=link_type,
            href="https://invalid.local",
            media_type="application/json",
            title="",
            hreflang="en",
            priority=0,
            dpp_id=None,
            active=True,
            managed_by_system=True,
            source_data_carrier_id=carrier_id,
            created_by_subject=created_by,
        )
        try:
            # Savepoint protects outer transaction from concurrent insert conflicts.
            async with self._session.begin_nested():
                self._session.add(link)
                await self._session.flush()
            return link
        except IntegrityError:
            result = await self._session.execute(
                select(ResolverLink).where(
                    ResolverLink.tenant_id == tenant_id,
                    ResolverLink.identifier == identifier,
                    ResolverLink.link_type == link_type,
                )
            )
            recovered = result.scalar_one_or_none()
            if recovered is None:
                raise
            recovered.managed_by_system = True
            recovered.source_data_carrier_id = carrier_id
            return recovered
