"""Pydantic schemas for the ESPR compliance rule engine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RuleDefinition(BaseModel):
    """A single compliance rule loaded from YAML."""

    id: str = Field(description="Unique rule identifier, e.g. BAT-001")
    field_path: str = Field(description="Dot-separated path into the AAS submodel element tree")
    condition: str = Field(
        description="Condition to evaluate: required, min_length, regex, enum, range"
    )
    severity: Literal["critical", "warning", "info"] = Field(default="warning")
    message: str = Field(description="Human-readable violation message")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Condition-specific parameters (e.g. min_length, pattern, allowed_values)",
    )
    semantic_id: str | None = Field(
        default=None,
        description="Optional semantic ID filter — rule only applies to submodels matching this",
    )


class ComplianceViolation(BaseModel):
    """A single rule violation found during compliance evaluation."""

    rule_id: str
    severity: Literal["critical", "warning", "info"]
    field_path: str
    message: str
    actual_value: Any | None = None


class ComplianceSummary(BaseModel):
    """Aggregate counts of a compliance evaluation."""

    total_rules: int
    passed: int
    critical_violations: int
    warnings: int
    info: int = 0


class ComplianceReport(BaseModel):
    """Full result of a compliance evaluation against one DPP."""

    dpp_id: UUID | None = None
    category: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_compliant: bool
    violations: list[ComplianceViolation] = Field(default_factory=list)
    summary: ComplianceSummary


class RuleCatalogEntry(BaseModel):
    """Public-facing rule metadata."""

    id: str
    field_path: str
    condition: str
    severity: Literal["critical", "warning", "info"]
    message: str
    semantic_id: str | None = None


class CategoryRuleset(BaseModel):
    """All rules for a product category."""

    category: str
    version: str
    description: str
    rules: list[RuleCatalogEntry]
