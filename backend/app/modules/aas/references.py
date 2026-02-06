"""Consolidated reference conversion utilities for BaSyx AAS model objects.

Extracted from duplicate implementations across definition.py, basyx_builder.py,
basyx_parser.py, mapping.py, and qualifiers.py.
"""

from __future__ import annotations

import re
from typing import Any

from basyx.aas import model

# Regex to convert CamelCase → UPPER_SNAKE_CASE for enum lookup
_CAMEL_TO_UPPER_SNAKE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

# Pre-built lookup: maps both UPPER_SNAKE ("GLOBAL_REFERENCE") and
# lowercase-no-separator ("globalreference") to KeyTypes members.
_KEY_TYPE_LOOKUP: dict[str, model.KeyTypes] = {}
for _kt in model.KeyTypes:
    _KEY_TYPE_LOOKUP[_kt.name] = _kt
    _KEY_TYPE_LOOKUP[_kt.name.replace("_", "").lower()] = _kt


def _resolve_key_type(raw: str) -> model.KeyTypes | None:
    """Resolve a key type string (CamelCase, UPPER_SNAKE, or mixed) to a KeyTypes enum."""
    # Try direct UPPER_SNAKE lookup first (fastest path)
    upper = raw.upper().replace(" ", "_")
    if upper in _KEY_TYPE_LOOKUP:
        return _KEY_TYPE_LOOKUP[upper]
    # Try CamelCase → UPPER_SNAKE conversion
    snake = _CAMEL_TO_UPPER_SNAKE.sub("_", raw).upper()
    if snake in _KEY_TYPE_LOOKUP:
        return _KEY_TYPE_LOOKUP[snake]
    # Try lowercased no-separator lookup (handles "globalreference")
    lower = raw.replace("_", "").replace(" ", "").lower()
    return _KEY_TYPE_LOOKUP.get(lower)


# Mapping from KeyTypes to model classes for constructing ModelReference.
# ModelReference requires a `type_` parameter pointing to the referred class.
_KEY_TYPE_TO_MODEL_CLASS: dict[model.KeyTypes, type] = {
    model.KeyTypes.SUBMODEL: model.Submodel,
    model.KeyTypes.ASSET_ADMINISTRATION_SHELL: model.AssetAdministrationShell,
    model.KeyTypes.CONCEPT_DESCRIPTION: model.ConceptDescription,  # type: ignore[attr-defined]
    model.KeyTypes.PROPERTY: model.Property,
    model.KeyTypes.SUBMODEL_ELEMENT_COLLECTION: model.SubmodelElementCollection,
    model.KeyTypes.SUBMODEL_ELEMENT_LIST: model.SubmodelElementList,
    model.KeyTypes.ENTITY: model.Entity,
    model.KeyTypes.FILE: model.File,
    model.KeyTypes.BLOB: model.Blob,
    model.KeyTypes.MULTI_LANGUAGE_PROPERTY: model.MultiLanguageProperty,
    model.KeyTypes.RANGE: model.Range,
    model.KeyTypes.REFERENCE_ELEMENT: model.ReferenceElement,
    model.KeyTypes.RELATIONSHIP_ELEMENT: model.RelationshipElement,
    model.KeyTypes.ANNOTATED_RELATIONSHIP_ELEMENT: model.AnnotatedRelationshipElement,
    model.KeyTypes.OPERATION: model.Operation,
    model.KeyTypes.CAPABILITY: model.Capability,
    model.KeyTypes.BASIC_EVENT_ELEMENT: model.BasicEventElement,
}


def reference_to_str(reference: model.Reference | None) -> str | None:
    """Extract the first key's value from a BaSyx Reference as a string.

    Works with both ``reference.key`` (older BaSyx) and ``reference.keys``.
    """
    if reference is None:
        return None
    keys = getattr(reference, "keys", None)
    if keys is None:
        keys = getattr(reference, "key", None)
    if not keys:
        return None
    first = next(iter(keys), None)
    if first is None:
        return None
    value = getattr(first, "value", None)
    return str(value) if value is not None else None


def reference_to_dict(reference: model.Reference | None) -> dict[str, Any] | None:
    """Serialize a BaSyx Reference to a JSON-friendly dict.

    Uses the reference's class name (``ModelReference`` or ``ExternalReference``)
    as the ``type`` field, and each key's ``type.name`` for the key type.
    """
    if reference is None:
        return None
    keys = getattr(reference, "keys", None)
    if keys is None:
        keys = getattr(reference, "key", None)
    if not keys:
        return None
    key_dicts = [
        {
            "type": key.type.name if hasattr(key.type, "name") else str(key.type),
            "value": key.value,
        }
        for key in keys
    ]
    return {
        "type": reference.__class__.__name__,
        "keys": key_dicts,
    }


def reference_from_dict(payload: Any) -> model.Reference | None:
    """Deserialize a dict into a BaSyx Reference (ModelReference or ExternalReference).

    Correctly constructs ``ModelReference`` when the dict specifies
    ``"type": "ModelReference"``, using the first key's type to determine
    the referred model class.
    """
    if not isinstance(payload, dict):
        return None
    keys = payload.get("keys")
    if not isinstance(keys, list):
        return None

    key_objs: list[model.Key] = []
    for entry in keys:
        if not isinstance(entry, dict):
            continue
        raw_type = str(entry.get("type", "")).strip()
        if not raw_type:
            continue
        key_type = _resolve_key_type(raw_type)
        if key_type is None:
            continue
        key_value = str(entry.get("value", ""))
        key_objs.append(model.Key(key_type, key_value))

    if not key_objs:
        return None

    key_tuple = tuple(key_objs)
    reference_type = str(payload.get("type", "")).lower()

    if reference_type == "modelreference":
        # Resolve the referred type from the first key's KeyType
        first_key_type = key_objs[0].type
        referred_type = _KEY_TYPE_TO_MODEL_CLASS.get(first_key_type)
        if referred_type is not None:
            return model.ModelReference(key=key_tuple, type_=referred_type)
        # Unknown key type — fall back to ExternalReference
        return model.ExternalReference(key=key_tuple)

    return model.ExternalReference(key=key_tuple)


def extract_semantic_id_str(obj: dict[str, Any]) -> str:
    """Extract the semantic ID string from a dict with ``semanticId`` or ``semanticID`` key.

    Works with the standard AAS JSON structure:
    ``{"semanticId": {"keys": [{"value": "..."}]}}``

    Also handles qualifier dicts that use ``semanticID`` (capital D).
    """
    semantic_id = obj.get("semanticId") or obj.get("semanticID")
    if isinstance(semantic_id, dict):
        keys = semantic_id.get("keys", [])
        if isinstance(keys, list) and keys:
            key_value = keys[0].get("value")
            if key_value:
                return str(key_value)
    return ""
