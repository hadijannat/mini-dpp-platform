"""Pydantic schemas for the LCA / Product Carbon Footprint calculation service."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

LCAScope = Literal["cradle-to-gate", "gate-to-gate", "cradle-to-grave"]


class EmissionFactor(BaseModel):
    """A single emission factor from the factor database."""

    material: str
    category: str
    factor_kg_co2e_per_kg: float
    source: str
    scope: str
    year: int


class MaterialItem(BaseModel):
    """A single material entry in a product's inventory."""

    material_name: str
    category: str
    mass_kg: float = Field(ge=0.0)
    quantity: int = Field(default=1, ge=1)
    pre_declared_pcf: float | None = None


class MaterialInventory(BaseModel):
    """Extracted material inventory from AAS submodels."""

    items: list[MaterialItem] = Field(default_factory=list)
    total_mass_kg: float = 0.0
    source_submodels: list[str] = Field(default_factory=list)


class MaterialBreakdown(BaseModel):
    """Per-material GWP breakdown in a PCF result."""

    material_name: str
    mass_kg: float
    factor_used: float
    gwp_kg_co2e: float
    source: str


class PCFResult(BaseModel):
    """Result of a PCF calculation from the stateless engine."""

    total_gwp_kg_co2e: float
    breakdown: list[MaterialBreakdown] = Field(default_factory=list)
    scope: str
    methodology: str


class LCARequest(BaseModel):
    """Request body for triggering an LCA calculation."""

    dpp_id: UUID
    scope: LCAScope | None = Field(
        default=None,
        description="LCA scope boundary. Defaults to config lca_default_scope.",
    )
    force_recalculate: bool = False


class LCAReport(BaseModel):
    """Full persisted LCA report returned to clients."""

    id: UUID
    dpp_id: UUID
    revision_no: int
    methodology: str
    scope: str
    total_gwp_kg_co2e: float
    impact_categories: dict[str, float] = Field(default_factory=dict)
    material_inventory: MaterialInventory
    factor_database_version: str
    created_at: datetime
    breakdown: list[MaterialBreakdown] = Field(default_factory=list)


class ComparisonRequest(BaseModel):
    """Request body for comparing PCF across two DPP revisions."""

    dpp_id: UUID
    revision_a: int = Field(ge=1)
    revision_b: int = Field(ge=1)


class ComparisonReport(BaseModel):
    """Side-by-side PCF comparison of two DPP revisions."""

    dpp_id: UUID
    revision_a: int
    revision_b: int
    report_a: LCAReport
    report_b: LCAReport
    delta_gwp_kg_co2e: float
    delta_percentage: float | None = None
