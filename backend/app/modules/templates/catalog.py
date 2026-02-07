"""Template catalog for IDTA Submodel Templates.

Centralizes template metadata (semantic IDs, repo folders, file patterns)
so the registry service does not hardcode these values.
"""

from __future__ import annotations

from dataclasses import dataclass


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

    def resolve_json_pattern(self) -> str:
        if self.json_pattern:
            return self.json_pattern
        return self.aasx_pattern.replace(".aasx", ".json")


TEMPLATE_CATALOG: dict[str, TemplateDescriptor] = {
    "digital-nameplate": TemplateDescriptor(
        key="digital-nameplate",
        title="Digital Nameplate",
        semantic_id="https://admin-shell.io/idta/nameplate/3/0/Nameplate",
        template_uri="https://admin-shell.io/idta/nameplate/3/0/Nameplate",
        repo_folder="Digital nameplate",
        baseline_major=3,
        baseline_minor=0,
        aasx_pattern="IDTA 02006-{major}-{minor}-{patch}_Template_Digital Nameplate.aasx",
    ),
    "contact-information": TemplateDescriptor(
        key="contact-information",
        title="Contact Information",
        semantic_id="https://admin-shell.io/zvei/nameplate/1/0/ContactInformations",
        template_uri="https://admin-shell.io/zvei/nameplate/1/0/ContactInformations",
        repo_folder="Contact Information",
        baseline_major=1,
        baseline_minor=0,
        aasx_pattern="IDTA 02002-{major}-{minor}-{patch}_Template_ContactInformation.aasx",
    ),
    "technical-data": TemplateDescriptor(
        key="technical-data",
        title="Technical Data",
        semantic_id="0173-1#01-AHX837#002",
        template_uri="0173-1#01-AHX837#002",
        repo_folder="Technical_Data",
        baseline_major=2,
        baseline_minor=0,
        aasx_pattern="IDTA 02003_{major}-{minor}-{patch}_Template_TechnicalData.aasx",
    ),
    "carbon-footprint": TemplateDescriptor(
        key="carbon-footprint",
        title="Carbon Footprint",
        semantic_id="https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/1/0",
        template_uri="https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/1/0",
        repo_folder="Carbon Footprint",
        baseline_major=1,
        baseline_minor=0,
        aasx_pattern="IDTA 02023-{major}-{minor}-{patch} _Template_CarbonFootprint.aasx",
    ),
    "handover-documentation": TemplateDescriptor(
        key="handover-documentation",
        title="Handover Documentation",
        semantic_id="0173-1#01-AHF578#003",
        template_uri="0173-1#01-AHF578#003",
        repo_folder="Handover Documentation",
        baseline_major=2,
        baseline_minor=0,
        aasx_pattern="IDTA 02004-{major}-{minor}-{patch}_Template_HandoverDocumentation.aasx",
    ),
    "hierarchical-structures": TemplateDescriptor(
        key="hierarchical-structures",
        title="Hierarchical Structures enabling Bills of Material",
        semantic_id="https://admin-shell.io/idta/HierarchicalStructures/1/1/Submodel",
        template_uri="https://admin-shell.io/idta/HierarchicalStructures/1/1/Submodel",
        repo_folder="Hierarchical Structures enabling Bills of Material",
        baseline_major=1,
        baseline_minor=1,
        aasx_pattern="IDTA 02011-{major}-{minor}-{patch}_Template_HSEBoM.aasx",
    ),
}

CORE_TEMPLATE_KEYS: tuple[str, ...] = (
    "carbon-footprint",
    "contact-information",
    "digital-nameplate",
    "handover-documentation",
    "hierarchical-structures",
    "technical-data",
)


def get_template_descriptor(template_key: str) -> TemplateDescriptor | None:
    return TEMPLATE_CATALOG.get(template_key)


def list_template_keys() -> list[str]:
    return list(CORE_TEMPLATE_KEYS)


def list_template_descriptors() -> list[TemplateDescriptor]:
    return [TEMPLATE_CATALOG[key] for key in CORE_TEMPLATE_KEYS]
