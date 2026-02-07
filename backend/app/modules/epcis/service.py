"""EPCIS 2.0 service — business logic for event capture and query.

Provides ``EPCISService`` for persisting and querying EPCIS events
linked to DPPs within a tenant context.
"""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import EPCISEvent, EPCISEventType

from .schemas import (
    AggregationEventCreate,
    AssociationEventCreate,
    CaptureResponse,
    EPCISDocumentCreate,
    EPCISEventResponse,
    EPCISEventUnion,
    EPCISQueryParams,
    ObjectEventCreate,
    TransactionEventCreate,
    TransformationEventCreate,
)

logger = get_logger(__name__)


class EPCISService:
    """DPP-aware EPCIS 2.0 event service.

    Usage::

        service = EPCISService(db_session)
        result = await service.capture(tenant_id, document, user_sub)
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    async def capture(
        self,
        tenant_id: UUID,
        dpp_id: UUID,
        document: EPCISDocumentCreate,
        created_by: str,
    ) -> CaptureResponse:
        """Validate and persist all events from an EPCIS document.

        Each event is mapped to an ``EPCISEvent`` row with common columns
        extracted and type-specific fields stored in the JSONB ``payload``.

        Returns:
            ``CaptureResponse`` with a capture UUID and event count.
        """
        capture_id = str(uuid.uuid4())
        count = 0

        for event in document.epcis_body.event_list:
            event_id = event.event_id or f"urn:uuid:{uuid.uuid4()}"
            event_type = EPCISEventType(event.type)

            # Extract type-specific payload
            payload = self._build_payload(event)

            # Extract error_declaration as dict if present
            error_decl: dict[str, Any] | None = None
            if event.error_declaration is not None:
                error_decl = event.error_declaration.model_dump(mode="json", by_alias=True)

            row = EPCISEvent(
                tenant_id=tenant_id,
                dpp_id=dpp_id,
                event_id=event_id,
                event_type=event_type,
                event_time=event.event_time,
                event_time_zone_offset=event.event_time_zone_offset,
                action=getattr(event, "action", None),
                biz_step=event.biz_step,
                disposition=event.disposition,
                read_point=event.read_point,
                biz_location=event.biz_location,
                payload=payload,
                error_declaration=error_decl,
                created_by_subject=created_by,
            )
            self._session.add(row)
            count += 1

        await self._session.flush()

        logger.info(
            "epcis_events_captured",
            capture_id=capture_id,
            tenant_id=str(tenant_id),
            dpp_id=str(dpp_id),
            event_count=count,
        )

        return CaptureResponse(capture_id=capture_id, event_count=count)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def query(
        self,
        tenant_id: UUID,
        filters: EPCISQueryParams,
    ) -> list[EPCISEventResponse]:
        """Query EPCIS events with SimpleEventQuery-style filters."""
        stmt = (
            select(EPCISEvent)
            .where(EPCISEvent.tenant_id == tenant_id)
            .order_by(EPCISEvent.event_time)
        )

        if filters.event_type is not None:
            stmt = stmt.where(EPCISEvent.event_type == filters.event_type)

        if filters.ge_event_time is not None:
            stmt = stmt.where(EPCISEvent.event_time >= filters.ge_event_time)

        if filters.lt_event_time is not None:
            stmt = stmt.where(EPCISEvent.event_time < filters.lt_event_time)

        if filters.eq_biz_step is not None:
            stmt = stmt.where(EPCISEvent.biz_step == filters.eq_biz_step)

        if filters.eq_disposition is not None:
            stmt = stmt.where(EPCISEvent.disposition == filters.eq_disposition)

        if filters.eq_read_point is not None:
            stmt = stmt.where(EPCISEvent.read_point == filters.eq_read_point)

        if filters.eq_biz_location is not None:
            stmt = stmt.where(EPCISEvent.biz_location == filters.eq_biz_location)

        if filters.dpp_id is not None:
            stmt = stmt.where(EPCISEvent.dpp_id == filters.dpp_id)

        if filters.match_epc is not None:
            # JSONB containment: payload @> '{"epcList": ["<epc>"]}'
            stmt = stmt.where(
                EPCISEvent.payload.op("@>")(
                    f'{{"epcList": ["{filters.match_epc}"]}}'
                )
            )

        stmt = stmt.limit(filters.limit).offset(filters.offset)

        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [EPCISEventResponse.model_validate(row) for row in rows]

    async def get_by_id(
        self,
        tenant_id: UUID,
        event_id: str,
    ) -> EPCISEventResponse | None:
        """Get a single EPCIS event by its event_id URI."""
        result = await self._session.execute(
            select(EPCISEvent).where(
                EPCISEvent.tenant_id == tenant_id,
                EPCISEvent.event_id == event_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return EPCISEventResponse.model_validate(row)

    async def get_for_dpp(
        self,
        tenant_id: UUID,
        dpp_id: UUID,
    ) -> list[EPCISEventResponse]:
        """Get all EPCIS events linked to a specific DPP, ordered by time."""
        result = await self._session.execute(
            select(EPCISEvent)
            .where(
                EPCISEvent.tenant_id == tenant_id,
                EPCISEvent.dpp_id == dpp_id,
            )
            .order_by(EPCISEvent.event_time)
        )
        rows = result.scalars().all()
        return [EPCISEventResponse.model_validate(row) for row in rows]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_payload(event: EPCISEventUnion) -> dict[str, Any]:
        """Extract type-specific fields into a JSONB-ready dict."""
        payload: dict[str, Any] = {}

        if isinstance(event, ObjectEventCreate):
            if event.epc_list:
                payload["epcList"] = event.epc_list
            if event.quantity_list:
                payload["quantityList"] = [
                    q.model_dump(mode="json", by_alias=True) for q in event.quantity_list
                ]
            if event.biz_transaction_list:
                payload["bizTransactionList"] = [
                    bt.model_dump(mode="json", by_alias=True) for bt in event.biz_transaction_list
                ]
            if event.ilmd is not None:
                payload["ilmd"] = event.ilmd

        elif isinstance(event, AggregationEventCreate):
            if event.parent_id:
                payload["parentID"] = event.parent_id
            if event.child_epcs:
                payload["childEPCs"] = event.child_epcs
            if event.child_quantity_list:
                payload["childQuantityList"] = [
                    q.model_dump(mode="json", by_alias=True) for q in event.child_quantity_list
                ]

        elif isinstance(event, TransactionEventCreate):
            payload["bizTransactionList"] = [
                bt.model_dump(mode="json", by_alias=True) for bt in event.biz_transaction_list
            ]
            if event.epc_list:
                payload["epcList"] = event.epc_list
            if event.quantity_list:
                payload["quantityList"] = [
                    q.model_dump(mode="json", by_alias=True) for q in event.quantity_list
                ]
            if event.parent_id:
                payload["parentID"] = event.parent_id

        elif isinstance(event, TransformationEventCreate):
            if event.input_epc_list:
                payload["inputEPCList"] = event.input_epc_list
            if event.input_quantity_list:
                payload["inputQuantityList"] = [
                    q.model_dump(mode="json", by_alias=True) for q in event.input_quantity_list
                ]
            if event.output_epc_list:
                payload["outputEPCList"] = event.output_epc_list
            if event.output_quantity_list:
                payload["outputQuantityList"] = [
                    q.model_dump(mode="json", by_alias=True) for q in event.output_quantity_list
                ]
            if event.transformation_id:
                payload["transformationID"] = event.transformation_id

        elif isinstance(event, AssociationEventCreate):
            if event.parent_id:
                payload["parentID"] = event.parent_id
            if event.child_epcs:
                payload["childEPCs"] = event.child_epcs
            if event.child_quantity_list:
                payload["childQuantityList"] = [
                    q.model_dump(mode="json", by_alias=True) for q in event.child_quantity_list
                ]

        # Sensor elements (common but stored in payload)
        if event.sensor_element_list:
            payload["sensorElementList"] = [
                se.model_dump(mode="json", by_alias=True, exclude_none=True)
                for se in event.sensor_element_list
            ]

        return payload
