"""Data carrier compliance profile settings and parsing helpers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.modules.data_carriers.schemas import (
    DataCarrierIdentifierScheme,
    DataCarrierIdentityLevel,
    DataCarrierStatus,
    DataCarrierType,
)

DATA_CARRIER_COMPLIANCE_PROFILE_KEY = "data_carrier_compliance_profile"
DATA_CARRIER_PUBLISH_GATE_ENABLED_KEY = "data_carrier_publish_gate_enabled"


class DataCarrierComplianceProfile(BaseModel):
    """Admin-configurable profile used by data carrier publish checks."""

    name: str = Field(default="generic_espr_v1", min_length=3, max_length=64)
    allowed_carrier_types: list[DataCarrierType] = Field(
        default_factory=lambda: [DataCarrierType.QR, DataCarrierType.DATAMATRIX]
    )
    default_identity_level: DataCarrierIdentityLevel = DataCarrierIdentityLevel.ITEM
    allowed_identity_levels: list[DataCarrierIdentityLevel] = Field(
        default_factory=lambda: [
            DataCarrierIdentityLevel.MODEL,
            DataCarrierIdentityLevel.BATCH,
            DataCarrierIdentityLevel.ITEM,
        ]
    )
    allowed_identifier_schemes: list[DataCarrierIdentifierScheme] = Field(
        default_factory=lambda: [
            DataCarrierIdentifierScheme.GS1_GTIN,
            DataCarrierIdentifierScheme.IEC61406,
            DataCarrierIdentifierScheme.DIRECT_URL,
        ]
    )
    publish_allowed_statuses: list[DataCarrierStatus] = Field(
        default_factory=lambda: [DataCarrierStatus.ACTIVE]
    )
    publish_require_active_carrier: bool = True
    publish_require_pre_sale_enabled: bool = False
    enforce_gtin_verified: bool = True

    @field_validator(
        "allowed_carrier_types",
        "allowed_identity_levels",
        "allowed_identifier_schemes",
        "publish_allowed_statuses",
        mode="after",
    )
    @classmethod
    def _dedupe_values(cls, values: list[Any]) -> list[Any]:
        deduped: list[Any] = []
        seen: set[str] = set()
        for value in values:
            key = str(getattr(value, "value", value))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(value)
        return deduped


def default_data_carrier_compliance_profile() -> DataCarrierComplianceProfile:
    """Return the default generic ESPR profile."""
    return DataCarrierComplianceProfile()


def parse_data_carrier_compliance_profile(
    raw: Any | None,
) -> DataCarrierComplianceProfile:
    """Parse and validate a stored profile payload with safe fallback."""
    if not isinstance(raw, dict):
        return default_data_carrier_compliance_profile()
    try:
        return DataCarrierComplianceProfile.model_validate(raw)
    except Exception:
        return default_data_carrier_compliance_profile()

