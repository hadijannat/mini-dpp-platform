"""AAS metamodel conformance validation.

Validates AAS environment dicts against the AAS metamodel by:
1. Round-tripping through BaSyx's JSON deserializer
2. Checking required fields on identifiable elements
3. Validating semantic ID structure on submodel elements

This module provides the ``validate_aas_environment`` function used
by the compliance engine (Contract B).
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from typing import Any

from basyx.aas import model
from basyx.aas.adapter import json as basyx_json

from app.core.logging import get_logger
from app.modules.aas.model_utils import walk_submodel_deep
from app.modules.aas.references import reference_to_str

logger = get_logger(__name__)

# Required top-level keys in an AAS environment dict.
_REQUIRED_ENV_KEYS = {"assetAdministrationShells", "submodels"}

# Required keys inside each AAS shell dict.
_REQUIRED_AAS_KEYS = {"id", "assetInformation"}

# Required keys inside assetInformation.
_REQUIRED_ASSET_INFO_KEYS = {"assetKind", "globalAssetId"}

# Required keys inside each submodel dict.
_REQUIRED_SUBMODEL_KEYS = {"id"}


@dataclass
class AASValidationResult:
    """Result of AAS environment validation."""

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_aas_environment(aas_env: dict[str, Any]) -> AASValidationResult:
    """Validate an AAS environment dict against the AAS metamodel.

    Performs three levels of validation:
    1. **Structural** — checks required keys exist in the dict
    2. **BaSyx round-trip** — deserializes via BaSyx to catch schema errors
    3. **Semantic** — validates semantic IDs on submodel elements

    Args:
        aas_env: AAS environment as a JSON-compatible dict.

    Returns:
        An :class:`AASValidationResult` with errors and warnings.
    """
    result = AASValidationResult()

    # --- 1. Structural validation ---
    _validate_structure(aas_env, result)
    if result.errors:
        result.is_valid = False
        return result

    # --- 2. BaSyx round-trip validation ---
    store = _validate_basyx_roundtrip(aas_env, result)
    if result.errors:
        result.is_valid = False
        return result

    # --- 3. Semantic validation ---
    if store is not None:
        _validate_semantics(store, result)

    result.is_valid = len(result.errors) == 0
    return result


def _validate_structure(
    aas_env: dict[str, Any],
    result: AASValidationResult,
) -> None:
    """Check that required top-level keys and nested structures exist."""
    missing_top = _REQUIRED_ENV_KEYS - set(aas_env.keys())
    for key in sorted(missing_top):
        result.errors.append(f"Missing required top-level key: '{key}'")

    if missing_top:
        return

    # Validate each AAS shell
    shells = aas_env.get("assetAdministrationShells", [])
    if not isinstance(shells, list):
        result.errors.append(
            "'assetAdministrationShells' must be a list"
        )
        return

    for idx, shell in enumerate(shells):
        if not isinstance(shell, dict):
            result.errors.append(
                f"assetAdministrationShells[{idx}] must be an object"
            )
            continue
        missing_aas = _REQUIRED_AAS_KEYS - set(shell.keys())
        for key in sorted(missing_aas):
            result.errors.append(
                f"assetAdministrationShells[{idx}]: "
                f"missing required key '{key}'"
            )

        # Validate assetInformation
        asset_info = shell.get("assetInformation")
        if isinstance(asset_info, dict):
            missing_ai = _REQUIRED_ASSET_INFO_KEYS - set(asset_info.keys())
            for key in sorted(missing_ai):
                result.warnings.append(
                    f"assetAdministrationShells[{idx}]."
                    f"assetInformation: missing '{key}'"
                )

    # Validate submodels
    submodels = aas_env.get("submodels", [])
    if not isinstance(submodels, list):
        result.errors.append("'submodels' must be a list")
        return

    for idx, sm in enumerate(submodels):
        if not isinstance(sm, dict):
            result.errors.append(f"submodels[{idx}] must be an object")
            continue
        missing_sm = _REQUIRED_SUBMODEL_KEYS - set(sm.keys())
        for key in sorted(missing_sm):
            result.errors.append(
                f"submodels[{idx}]: missing required key '{key}'"
            )
        if "semanticId" not in sm:
            result.warnings.append(
                f"submodels[{idx}] (id={sm.get('id', '?')}): "
                f"missing semanticId"
            )


def _validate_basyx_roundtrip(
    aas_env: dict[str, Any],
    result: AASValidationResult,
) -> model.DictObjectStore[model.Identifiable] | None:
    """Deserialize via BaSyx and re-serialize to detect schema violations.

    Uses lenient mode first to recover as many objects as possible, then
    attempts strict mode to surface hard errors.
    """
    payload = json.dumps(aas_env, sort_keys=True, ensure_ascii=False)

    # Lenient pass — collects objects even if some entries are malformed
    string_io = io.StringIO(payload)
    try:
        store: model.DictObjectStore[model.Identifiable] = (
            basyx_json.read_aas_json_file(  # type: ignore[attr-defined]
                string_io
            )
        )
    except Exception as exc:
        result.errors.append(f"BaSyx deserialization failed: {exc}")
        return None
    finally:
        string_io.close()

    # Strict pass — detect objects skipped in lenient mode
    strict_io = io.StringIO(payload)
    try:
        basyx_json.read_aas_json_file(  # type: ignore[attr-defined]
            strict_io, failsafe=False
        )
    except Exception as exc:
        result.errors.append(f"BaSyx strict deserialization failed: {exc}")
    finally:
        strict_io.close()

    identifiables = list(store)
    if not identifiables:
        # Count expected objects from the dict
        expected = len(aas_env.get("assetAdministrationShells", []))
        expected += len(aas_env.get("submodels", []))
        expected += len(aas_env.get("conceptDescriptions", []))
        if expected > 0:
            result.warnings.append(
                "BaSyx deserialized zero identifiable objects "
                f"(expected {expected} from the environment dict)"
            )
        return store

    # Verify round-trip serialization works
    try:
        basyx_json.object_store_to_json(store)  # type: ignore[attr-defined]
    except Exception as exc:
        result.errors.append(
            f"BaSyx re-serialization failed (round-trip broken): {exc}"
        )

    return store


def _validate_semantics(
    store: model.DictObjectStore[model.Identifiable],
    result: AASValidationResult,
) -> None:
    """Check semantic ID presence and element-type consistency."""
    submodels = [obj for obj in store if isinstance(obj, model.Submodel)]

    for sm in submodels:
        sm_id = sm.id or sm.id_short or "?"
        sem_id = reference_to_str(sm.semantic_id)
        if not sem_id:
            result.warnings.append(
                f"Submodel '{sm_id}' has no semanticId"
            )

        for element in walk_submodel_deep(sm):
            _check_element_semantic(element, sm_id, result)


def _check_element_semantic(
    element: model.SubmodelElement,
    submodel_id: str,
    result: AASValidationResult,
) -> None:
    """Validate a single submodel element's semantic ID and type coherence."""
    id_short = getattr(element, "id_short", None) or "?"
    sem_id = reference_to_str(element.semantic_id)

    # Properties should ideally have a semantic ID
    if isinstance(element, model.Property) and not sem_id:
        result.warnings.append(
            f"Property '{id_short}' in submodel '{submodel_id}' "
            f"has no semanticId"
        )

    # Properties with empty value_type are suspicious
    if isinstance(element, model.Property):
        vt = getattr(element, "value_type", None)
        if vt is None:
            result.warnings.append(
                f"Property '{id_short}' in submodel '{submodel_id}' "
                f"has no valueType"
            )
