"""IDTA 01002-3-0 standard Pydantic models for AAS API responses.

Provides cursor-based pagination, service description, and standard
error format schemas per the IDTA AAS API specification.
"""

import base64
import binascii
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field


class IDTAMessage(BaseModel):
    """Standard IDTA message format for API responses."""

    code: str
    correlation_id: str | None = Field(default=None, alias="correlationId")
    message_type: Literal["Undefined", "Info", "Warning", "Error", "Exception"] = Field(
        alias="messageType"
    )
    text: str
    timestamp: str

    model_config = ConfigDict(populate_by_name=True)


class IDTAResult(BaseModel):
    """Standard IDTA result wrapper with messages."""

    messages: list[IDTAMessage] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class PagingMetadata(BaseModel):
    """Cursor-based pagination metadata per IDTA spec."""

    cursor: str | None = None


class PagedResult[T](BaseModel):
    """Generic paged result wrapper with cursor pagination."""

    result: list[T]
    paging_metadata: PagingMetadata = Field(alias="pagingMetadata")

    model_config = ConfigDict(populate_by_name=True)


class ServiceDescription(BaseModel):
    """IDTA-01002 $metadata / service-description response."""

    profiles: list[str]


# -- Cursor helpers ----------------------------------------------------------


def encode_cursor(uuid: UUID) -> str:
    """Encode a UUID as a base64url cursor string (no padding)."""
    return base64.urlsafe_b64encode(uuid.bytes).rstrip(b"=").decode()


def decode_cursor(cursor: str) -> UUID:
    """Decode a base64url cursor string back to a UUID.

    Raises HTTPException(400) if the cursor is malformed.
    """
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded)
        return UUID(bytes=raw)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc
