"""AAS submodel data extractor for material inventory.

Walks AAS environment dicts looking for BOM / hierarchical-structures
submodels to extract material names, masses, and any pre-declared PCF
values from carbon-footprint submodels.

This is a best-effort extraction — real AAS submodels vary widely in
structure, so the extractor uses heuristic idShort matching.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.modules.lca.schemas import MaterialInventory, MaterialItem

logger = get_logger(__name__)

# Semantic ID fragments used to identify relevant submodels
_BOM_SEMANTIC_IDS = (
    "HierarchicalStructures",
    "BillOfMaterial",
    "BOM",
)

_CARBON_FOOTPRINT_SEMANTIC_IDS = (
    "CarbonFootprint",
    "ProductCarbonFootprint",
)

# idShort fragments that indicate mass/weight properties
_MASS_ID_SHORTS = ("mass", "weight", "netweight", "grossweight")

# idShort fragments that indicate component/node collections
_COMPONENT_ID_SHORTS = ("component", "node", "part", "material", "entry")


def extract_material_inventory(aas_env: dict[str, Any]) -> MaterialInventory:
    """Extract a material inventory from an AAS environment dict.

    Walks submodels looking for BOM/hierarchical structures to find
    component entries with material names and masses. Also checks
    carbon-footprint submodels for pre-declared PCF values.

    Returns a ``MaterialInventory`` — possibly empty if no BOM data
    is found.
    """
    submodels = aas_env.get("submodels", [])
    if not isinstance(submodels, list):
        logger.warning("no_submodels_in_aas_env")
        return MaterialInventory()

    items: list[MaterialItem] = []
    source_submodels: list[str] = []
    pcf_values: dict[str, float] = {}

    # First pass: collect pre-declared PCF values from carbon footprint submodels
    for sm in submodels:
        if not isinstance(sm, dict):
            continue
        if _matches_semantic_id(sm, _CARBON_FOOTPRINT_SEMANTIC_IDS):
            pcf_values.update(_extract_pcf_values(sm))

    # Second pass: extract material items from BOM submodels
    for sm in submodels:
        if not isinstance(sm, dict):
            continue
        if _matches_semantic_id(sm, _BOM_SEMANTIC_IDS):
            sm_id = sm.get("idShort", "unknown")
            source_submodels.append(sm_id)
            items.extend(_extract_components(sm, pcf_values))

    if not items:
        logger.warning("no_material_items_extracted")

    total_mass = sum(i.mass_kg * i.quantity for i in items)

    return MaterialInventory(
        items=items,
        total_mass_kg=round(total_mass, 6),
        source_submodels=source_submodels,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _matches_semantic_id(
    submodel: dict[str, Any],
    fragments: tuple[str, ...],
) -> bool:
    """Check if a submodel's semanticId contains any of the fragments."""
    sem_id = submodel.get("semanticId", {})
    if isinstance(sem_id, dict):
        keys = sem_id.get("keys", [])
        if isinstance(keys, list):
            for key in keys:
                if isinstance(key, dict):
                    value = str(key.get("value", ""))
                    if any(f.lower() in value.lower() for f in fragments):
                        return True
    return False


def _extract_components(
    submodel: dict[str, Any],
    pcf_values: dict[str, float],
) -> list[MaterialItem]:
    """Extract material items from a BOM submodel's elements."""
    elements = submodel.get("submodelElements", [])
    if not isinstance(elements, list):
        return []

    items: list[MaterialItem] = []

    for elem in elements:
        if not isinstance(elem, dict):
            continue
        id_short = str(elem.get("idShort", "")).lower()

        # Look for collections that represent components
        if any(frag in id_short for frag in _COMPONENT_ID_SHORTS):
            item = _parse_component_element(elem, pcf_values)
            if item is not None:
                items.append(item)
        # Also recurse into generic SubmodelElementCollections
        elif elem.get("modelType") == "SubmodelElementCollection":
            nested = _extract_components(
                {"submodelElements": elem.get("value", [])},
                pcf_values,
            )
            items.extend(nested)

    return items


def _parse_component_element(
    element: dict[str, Any],
    pcf_values: dict[str, float],
) -> MaterialItem | None:
    """Parse a component element into a MaterialItem."""
    id_short = element.get("idShort", "")
    material_name = id_short

    # If the element has a value list (SubmodelElementCollection),
    # look for name, mass, and category properties
    values = element.get("value", [])
    mass_kg = 0.0
    category = "unknown"
    quantity = 1

    if isinstance(values, list):
        for prop in values:
            if not isinstance(prop, dict):
                continue
            prop_id = str(prop.get("idShort", "")).lower()
            prop_value = prop.get("value")

            if prop_id in ("materialname", "material", "name"):
                material_name = str(prop_value or id_short)
            elif any(m in prop_id for m in _MASS_ID_SHORTS):
                mass_kg = _safe_float(prop_value)
            elif prop_id in ("category", "materialcategory", "type"):
                category = str(prop_value or "unknown")
            elif prop_id in ("quantity", "count", "amount"):
                quantity = max(1, _safe_int(prop_value))
    elif isinstance(values, str):
        # Simple property with a string value — treat idShort as name
        material_name = id_short

    if not material_name:
        return None

    # Check for pre-declared PCF
    pre_declared = pcf_values.get(material_name.lower())

    return MaterialItem(
        material_name=material_name,
        category=category,
        mass_kg=mass_kg,
        quantity=quantity,
        pre_declared_pcf=pre_declared,
    )


def _extract_pcf_values(submodel: dict[str, Any]) -> dict[str, float]:
    """Extract pre-declared PCF values from a carbon footprint submodel."""
    result: dict[str, float] = {}
    elements = submodel.get("submodelElements", [])
    if not isinstance(elements, list):
        return result

    for elem in elements:
        if not isinstance(elem, dict):
            continue
        id_short = str(elem.get("idShort", "")).lower()
        if "pcf" in id_short or "carbonfootprint" in id_short:
            value = _safe_float(elem.get("value"))
            if value > 0:
                # Use the idShort (normalised) as key
                result[id_short] = value

    return result


def _safe_float(value: Any) -> float:
    """Safely convert a value to float."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _safe_int(value: Any) -> int:
    """Safely convert a value to int."""
    if value is None:
        return 1
    try:
        return int(value)
    except (ValueError, TypeError):
        return 1
