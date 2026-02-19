"""OPC UA subscription and data change handling."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.modules.opcua.transform import TransformError, apply_transform
from app.opcua_agent.ingestion_buffer import IngestionBuffer

logger = logging.getLogger("opcua_agent.subscription")


class DataChangeHandler:
    """Handles OPC UA data change notifications for a single mapping.

    Each handler instance is bound to one (tenant, DPP, mapping) triple
    and pushes transformed values into the shared ingestion buffer.
    """

    def __init__(
        self,
        *,
        buffer: IngestionBuffer,
        tenant_id: UUID,
        dpp_id: UUID,
        mapping_id: UUID,
        target_submodel_id: str,
        target_aas_path: str,
        transform_expr: str | None,
    ) -> None:
        self._buffer = buffer
        self._tenant_id = tenant_id
        self._dpp_id = dpp_id
        self._mapping_id = mapping_id
        self._target_submodel_id = target_submodel_id
        self._target_aas_path = target_aas_path
        self._transform_expr = transform_expr

    async def datachange_notification(
        self,
        node: Any,  # noqa: ARG002
        val: Any,
        data: Any,  # noqa: ARG002
    ) -> None:
        """Called by asyncua when a monitored node value changes.

        Applies the optional transform expression and puts the result
        into the ingestion buffer.

        Args:
            node: The asyncua Node that changed (unused but required by protocol).
            val: The new value.
            data: Full monitored item notification (unused but required by protocol).
        """
        try:
            value = val
            if self._transform_expr:
                try:
                    value = apply_transform(self._transform_expr, value)
                except TransformError:
                    logger.warning(
                        "Transform failed for mapping %s (expr=%r, value=%r)",
                        self._mapping_id,
                        self._transform_expr,
                        val,
                        exc_info=True,
                    )
                    return

            await self._buffer.put(
                tenant_id=self._tenant_id,
                dpp_id=self._dpp_id,
                mapping_id=self._mapping_id,
                target_submodel_id=self._target_submodel_id,
                target_aas_path=self._target_aas_path,
                value=value,
                timestamp=datetime.now(tz=UTC),
            )
        except Exception:
            logger.exception(
                "Unexpected error in datachange_notification for mapping %s",
                self._mapping_id,
            )
