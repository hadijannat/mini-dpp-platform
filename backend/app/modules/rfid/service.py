"""Service layer for RFID TDS sidecar integration and read ingestion."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import DPP, DataCarrier, DPPStatus, EPCISEvent, EPCISEventType
from app.modules.epcis.digital_link import parse_digital_link
from app.modules.rfid.schemas import (
    RFIDDecodeRequest,
    RFIDDecodeResponse,
    RFIDEncodeRequest,
    RFIDEncodeResponse,
    RFIDGS1Key,
    RFIDReadIngestResult,
    RFIDReadsIngestRequest,
    RFIDReadsIngestResponse,
)
from app.modules.tenant_domains.service import TenantDomainService

logger = get_logger(__name__)


class RFIDError(ValueError):
    """Raised when RFID operations fail."""


class RFIDSidecarUnavailableError(RFIDError):
    """Raised when RFID sidecar is unavailable."""


class RfidTdsClient:
    """HTTP client for RFID TDS sidecar service."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def _base_url(self) -> str:
        base_url = (self._settings.rfid_tds_service_url or "").strip().rstrip("/")
        if not base_url:
            raise RFIDSidecarUnavailableError("RFID sidecar URL is not configured")
        return base_url

    async def encode(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._post_json("/v1/encode", payload)

    async def decode(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._post_json("/v1/decode", payload)

    async def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        timeout = self._settings.rfid_tds_timeout_seconds
        url = f"{self._base_url()}{path}"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            raise RFIDSidecarUnavailableError(f"RFID sidecar request failed: {exc}") from exc

        if response.status_code >= 500:
            raise RFIDSidecarUnavailableError("RFID sidecar returned server error")
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = {"message": response.text}
            raise RFIDError(f"RFID sidecar rejected payload: {detail}")

        try:
            data = response.json()
        except ValueError as exc:
            raise RFIDSidecarUnavailableError("RFID sidecar returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise RFIDSidecarUnavailableError("RFID sidecar returned unexpected payload")
        return data


class RFIDService:
    """RFID business logic for encode/decode and read ingestion."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._client = RfidTdsClient()

    async def encode(self, *, tenant_id: UUID, request: RFIDEncodeRequest) -> RFIDEncodeResponse:
        hostname = request.hostname
        if not hostname and not request.digital_link:
            domain = await TenantDomainService(self._session).get_primary_active_domain(tenant_id)
            if domain is None:
                raise RFIDError("No active tenant domain is configured")
            hostname = domain.hostname

        digital_link = request.digital_link
        if not digital_link and hostname and request.gtin and request.serial:
            digital_link = self._build_digital_link(hostname, request.gtin, request.serial)

        payload = {
            "tdsScheme": request.tds_scheme,
            "digitalLink": digital_link,
            "hostname": hostname,
            "gtin": request.gtin,
            "serial": request.serial,
            "tagLength": request.tag_length,
            "filter": request.filter,
            "gs1CompanyPrefixLength": request.gs1_company_prefix_length,
        }
        data = await self._client.encode(payload)
        response = self._to_encode_response(data)
        logger.info(
            "rfid_encode_success",
            tenant_id=str(tenant_id),
            tds_scheme=response.tds_scheme,
            hostname=response.hostname,
            gtin=response.gs1_key.gtin,
        )
        return response

    async def decode(
        self,
        request: RFIDDecodeRequest,
        *,
        tenant_id: UUID | None = None,
    ) -> RFIDDecodeResponse:
        data = await self._client.decode({"epcHex": request.epc_hex, "tagLength": request.tag_length})
        response = self._to_decode_response(data)
        response = await self._ensure_digital_link(response, tenant_id=tenant_id)
        logger.info(
            "rfid_decode_success",
            tds_scheme=response.tds_scheme,
            hostname=response.hostname,
            gtin=response.gs1_key.gtin,
        )
        return response

    async def ingest_reads(
        self,
        *,
        tenant_id: UUID,
        created_by: str,
        request: RFIDReadsIngestRequest,
    ) -> RFIDReadsIngestResponse:
        results: list[RFIDReadIngestResult] = []
        created_events = 0
        matched_reads = 0

        for read in request.reads:
            try:
                decoded = await self.decode(
                    RFIDDecodeRequest(epc_hex=read.epc_hex, tag_length=read.tag_length),
                    tenant_id=tenant_id,
                )
                dpp_id = await self._find_matching_dpp_id(
                    tenant_id=tenant_id,
                    gs1_key=decoded.gs1_key,
                )
                if dpp_id is None:
                    results.append(
                        RFIDReadIngestResult(
                            epc_hex=read.epc_hex,
                            matched=False,
                            digital_link=decoded.digital_link,
                            error="No matching DPP found",
                        )
                    )
                    continue

                event_id = f"urn:uuid:{uuid.uuid4()}"
                event_time = read.observed_at or datetime.now(UTC)
                payload = {
                    "epcList": [decoded.tag_uri or decoded.pure_identity_uri or read.epc_hex],
                    "digitalLinkURI": decoded.digital_link,
                    "readerId": request.reader_id,
                    "antenna": read.antenna,
                    "rssi": read.rssi,
                    "epcHex": read.epc_hex,
                }
                row = EPCISEvent(
                    tenant_id=tenant_id,
                    dpp_id=dpp_id,
                    event_id=event_id,
                    event_type=EPCISEventType.OBJECT,
                    event_time=event_time,
                    event_time_zone_offset="+00:00",
                    action="OBSERVE",
                    biz_step="receiving",
                    disposition=None,
                    read_point=request.read_point,
                    biz_location=request.biz_location,
                    payload=payload,
                    error_declaration=None,
                    created_by_subject=created_by,
                )
                self._session.add(row)
                created_events += 1
                matched_reads += 1
                results.append(
                    RFIDReadIngestResult(
                        epc_hex=read.epc_hex,
                        matched=True,
                        dpp_id=dpp_id,
                        event_id=event_id,
                        digital_link=decoded.digital_link,
                    )
                )
            except RFIDError as exc:
                logger.warning(
                    "rfid_ingest_decode_failed",
                    tenant_id=str(tenant_id),
                    epc_hex=read.epc_hex,
                    error=str(exc),
                )
                results.append(
                    RFIDReadIngestResult(
                        epc_hex=read.epc_hex,
                        matched=False,
                        error=str(exc),
                    )
                )

        await self._session.flush()
        logger.info(
            "rfid_ingest_completed",
            tenant_id=str(tenant_id),
            reader_id=request.reader_id,
            total_reads=len(request.reads),
            matched_reads=matched_reads,
            created_events=created_events,
        )
        return RFIDReadsIngestResponse(
            reader_id=request.reader_id,
            total_reads=len(request.reads),
            matched_reads=matched_reads,
            created_events=created_events,
            results=results,
        )

    async def _find_matching_dpp_id(
        self,
        *,
        tenant_id: UUID,
        gs1_key: RFIDGS1Key,
    ) -> UUID | None:
        if gs1_key.gtin and gs1_key.serial:
            identifier_key = f"01/{gs1_key.gtin}/21/{gs1_key.serial}"
            by_carrier = await self._session.execute(
                select(DataCarrier.dpp_id)
                .where(
                    DataCarrier.tenant_id == tenant_id,
                    DataCarrier.identifier_key == identifier_key,
                )
                .limit(1)
            )
            dpp_id = by_carrier.scalar_one_or_none()
            if dpp_id is not None:
                return dpp_id

        rows = await self._session.execute(
            select(DPP.id, DPP.asset_ids).where(
                DPP.tenant_id == tenant_id,
                DPP.status == DPPStatus.PUBLISHED,
            )
        )
        for dpp_id, asset_ids in rows.all():
            if not isinstance(asset_ids, dict):
                continue
            gtin = str(asset_ids.get("gtin", "")).strip()
            serial = str(asset_ids.get("serialNumber", "")).strip()
            if gtin and serial and gtin == (gs1_key.gtin or "") and serial == (gs1_key.serial or ""):
                return dpp_id
        return None

    @staticmethod
    def _build_digital_link(hostname: str, gtin: str, serial: str) -> str:
        return (
            f"https://{hostname.strip().lower().rstrip('.')}"
            f"/01/{gtin.strip()}/21/{serial.strip()}"
        )

    async def _ensure_digital_link(
        self,
        response: RFIDDecodeResponse,
        *,
        tenant_id: UUID | None,
    ) -> RFIDDecodeResponse:
        if response.digital_link:
            return response
        if not response.gs1_key.gtin or not response.gs1_key.serial:
            return response

        hostname = response.hostname
        if not hostname and tenant_id is not None:
            domain = await TenantDomainService(self._session).get_primary_active_domain(tenant_id)
            hostname = domain.hostname if domain is not None else None
        if not hostname:
            return response

        digital_link = self._build_digital_link(hostname, response.gs1_key.gtin, response.gs1_key.serial)
        return response.model_copy(update={"hostname": hostname, "digital_link": digital_link})

    @staticmethod
    def _to_encode_response(payload: dict[str, Any]) -> RFIDEncodeResponse:
        fields = RFIDService._coerce_fields(payload.get("fields"))
        gtin = payload.get("gtin") or fields.get("gtin")
        serial = payload.get("serial") or fields.get("serial")
        digital_link = payload.get("digitalLink") or payload.get("digital_link")
        if not digital_link:
            digital_link = fields.get("digitalLinkURI")
        if digital_link and (not gtin or not serial):
            try:
                parsed = parse_digital_link(str(digital_link))
                gtin = gtin or parsed.get("gtin")
                serial = serial or parsed.get("serial")
            except ValueError:
                pass
        hostname = payload.get("hostname") or fields.get("hostname") or fields.get("domain")
        return RFIDEncodeResponse(
            tds_scheme=str(payload.get("tdsScheme") or payload.get("tds_scheme") or "sgtin++"),
            tag_length=int(payload.get("tagLength") or payload.get("tag_length") or 96),
            epc_hex=str(payload.get("epcHex") or payload.get("epc_hex") or ""),
            tag_uri=RFIDService._maybe_str(payload.get("tagUri") or payload.get("tag_uri")),
            pure_identity_uri=RFIDService._maybe_str(
                payload.get("pureIdentityUri") or payload.get("pure_identity_uri")
            ),
            digital_link=RFIDService._maybe_str(digital_link),
            hostname=RFIDService._maybe_str(hostname),
            gs1_key=RFIDGS1Key(
                gtin=RFIDService._maybe_str(gtin),
                serial=RFIDService._maybe_str(serial),
            ),
            fields=fields,
        )

    @staticmethod
    def _to_decode_response(payload: dict[str, Any]) -> RFIDDecodeResponse:
        fields = RFIDService._coerce_fields(payload.get("fields"))
        gtin = payload.get("gtin") or fields.get("gtin")
        serial = payload.get("serial") or fields.get("serial")
        digital_link = payload.get("digitalLink") or payload.get("digital_link")
        if not digital_link:
            digital_link = fields.get("digitalLinkURI")
        if digital_link and (not gtin or not serial):
            try:
                parsed = parse_digital_link(str(digital_link))
                gtin = gtin or parsed.get("gtin")
                serial = serial or parsed.get("serial")
            except ValueError:
                pass
        hostname = payload.get("hostname") or fields.get("hostname") or fields.get("domain")
        return RFIDDecodeResponse(
            tds_scheme=str(payload.get("tdsScheme") or payload.get("tds_scheme") or "sgtin++"),
            tag_length=int(payload.get("tagLength") or payload.get("tag_length") or 96),
            epc_hex=str(payload.get("epcHex") or payload.get("epc_hex") or ""),
            tag_uri=RFIDService._maybe_str(payload.get("tagUri") or payload.get("tag_uri")),
            pure_identity_uri=RFIDService._maybe_str(
                payload.get("pureIdentityUri") or payload.get("pure_identity_uri")
            ),
            digital_link=RFIDService._maybe_str(digital_link),
            hostname=RFIDService._maybe_str(hostname),
            gs1_key=RFIDGS1Key(
                gtin=RFIDService._maybe_str(gtin),
                serial=RFIDService._maybe_str(serial),
            ),
            fields=fields,
        )

    @staticmethod
    def _coerce_fields(value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        output: dict[str, str] = {}
        for key, raw in value.items():
            output[str(key)] = str(raw)
        return output

    @staticmethod
    def _maybe_str(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
