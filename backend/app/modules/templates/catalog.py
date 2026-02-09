"""Template catalog for IDTA Submodel Templates.

Centralizes template metadata (semantic IDs, repo folders, file patterns)
so the registry service does not hardcode these values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.modules.semantic_registry import (
    get_template_semantic_id,
    get_template_support_status,
    is_template_refresh_enabled,
)

SupportStatus = Literal["supported", "experimental", "unavailable"]


@dataclass(frozen=True)
class TemplateDescriptor:
    key: str
    title: str
    semantic_id: str
    template_uri: str
    repo_folder: str
    baseline_major: int
    baseline_minor: int
    aasx_pattern: str
    json_pattern: str | None = None
    support_status: SupportStatus = "supported"
    refresh_enabled: bool = True

    def resolve_json_pattern(self) -> str:
        if self.json_pattern:
            return self.json_pattern
        return self.aasx_pattern.replace(".aasx", ".json")


def _semantic_id(template_key: str) -> str:
    semantic_id = get_template_semantic_id(template_key)
    if not semantic_id:
        raise RuntimeError(f"Missing semantic registry entry for template '{template_key}'")
    return semantic_id


def _support_status(template_key: str) -> SupportStatus:
    return get_template_support_status(template_key)


def _refresh_enabled(template_key: str) -> bool:
    return is_template_refresh_enabled(template_key)


TEMPLATE_CATALOG: dict[str, TemplateDescriptor] = {
    "digital-nameplate": TemplateDescriptor(
        key="digital-nameplate",
        title="Digital Nameplate",
        semantic_id=_semantic_id("digital-nameplate"),
        template_uri=_semantic_id("digital-nameplate"),
        repo_folder="Digital nameplate",
        baseline_major=3,
        baseline_minor=0,
        aasx_pattern="IDTA 02006-{major}-{minor}-{patch}_Template_Digital Nameplate.aasx",
        support_status=_support_status("digital-nameplate"),
        refresh_enabled=_refresh_enabled("digital-nameplate"),
    ),
    "contact-information": TemplateDescriptor(
        key="contact-information",
        title="Contact Information",
        semantic_id=_semantic_id("contact-information"),
        template_uri=_semantic_id("contact-information"),
        repo_folder="Contact Information",
        baseline_major=1,
        baseline_minor=0,
        aasx_pattern="IDTA 02002-{major}-{minor}-{patch}_Template_ContactInformation.aasx",
        support_status=_support_status("contact-information"),
        refresh_enabled=_refresh_enabled("contact-information"),
    ),
    "technical-data": TemplateDescriptor(
        key="technical-data",
        title="Technical Data",
        semantic_id=_semantic_id("technical-data"),
        template_uri=_semantic_id("technical-data"),
        repo_folder="Technical_Data",
        baseline_major=2,
        baseline_minor=0,
        aasx_pattern="IDTA 02003_{major}-{minor}-{patch}_Template_TechnicalData.aasx",
        support_status=_support_status("technical-data"),
        refresh_enabled=_refresh_enabled("technical-data"),
    ),
    "carbon-footprint": TemplateDescriptor(
        key="carbon-footprint",
        title="Carbon Footprint",
        semantic_id=_semantic_id("carbon-footprint"),
        template_uri=_semantic_id("carbon-footprint"),
        repo_folder="Carbon Footprint",
        baseline_major=1,
        baseline_minor=0,
        aasx_pattern="IDTA 02023-{major}-{minor}-{patch} _Template_CarbonFootprint.aasx",
        support_status=_support_status("carbon-footprint"),
        refresh_enabled=_refresh_enabled("carbon-footprint"),
    ),
    "handover-documentation": TemplateDescriptor(
        key="handover-documentation",
        title="Handover Documentation",
        semantic_id=_semantic_id("handover-documentation"),
        template_uri=_semantic_id("handover-documentation"),
        repo_folder="Handover Documentation",
        baseline_major=2,
        baseline_minor=0,
        aasx_pattern="IDTA 02004-{major}-{minor}-{patch}_Template_HandoverDocumentation.aasx",
        support_status=_support_status("handover-documentation"),
        refresh_enabled=_refresh_enabled("handover-documentation"),
    ),
    "hierarchical-structures": TemplateDescriptor(
        key="hierarchical-structures",
        title="Hierarchical Structures enabling Bills of Material",
        semantic_id=_semantic_id("hierarchical-structures"),
        template_uri=_semantic_id("hierarchical-structures"),
        repo_folder="Hierarchical Structures enabling Bills of Material",
        baseline_major=1,
        baseline_minor=1,
        aasx_pattern="IDTA 02011-{major}-{minor}-{patch}_Template_HSEBoM.aasx",
        support_status=_support_status("hierarchical-structures"),
        refresh_enabled=_refresh_enabled("hierarchical-structures"),
    ),
    "battery-passport": TemplateDescriptor(
        key="battery-passport",
        title="Battery Passport",
        semantic_id=_semantic_id("battery-passport"),
        template_uri=_semantic_id("battery-passport"),
        repo_folder="Battery Passport",
        baseline_major=1,
        baseline_minor=0,
        aasx_pattern=("IDTA 02035-{major}-{minor}-{patch}_Template_BatteryPassport.aasx"),
        support_status=_support_status("battery-passport"),
        refresh_enabled=_refresh_enabled("battery-passport"),
    ),
}

CORE_TEMPLATE_KEYS: tuple[str, ...] = (
    "battery-passport",
    "carbon-footprint",
    "contact-information",
    "digital-nameplate",
    "handover-documentation",
    "hierarchical-structures",
    "technical-data",
)


def get_template_descriptor(template_key: str) -> TemplateDescriptor | None:
    return TEMPLATE_CATALOG.get(template_key)


def list_template_keys(
    *,
    include_unavailable: bool = True,
    refreshable_only: bool = False,
) -> list[str]:
    keys: list[str] = []
    for key in CORE_TEMPLATE_KEYS:
        descriptor = TEMPLATE_CATALOG[key]
        if refreshable_only and not descriptor.refresh_enabled:
            continue
        if not include_unavailable and descriptor.support_status == "unavailable":
            continue
        keys.append(key)
    return keys


def list_template_descriptors() -> list[TemplateDescriptor]:
    return [TEMPLATE_CATALOG[key] for key in CORE_TEMPLATE_KEYS]
