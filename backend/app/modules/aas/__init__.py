"""Shared AAS/BaSyx utilities for reference handling, model operations, and traversal."""

from app.modules.aas.conformance import AASValidationResult, validate_aas_environment
from app.modules.aas.model_utils import (
    clear_parent,
    clone_identifiable,
    enum_to_str,
    iterable_attr,
    lang_string_set_to_dict,
    walk_submodel_deep,
)
from app.modules.aas.references import (
    extract_semantic_id_str,
    reference_from_dict,
    reference_to_dict,
    reference_to_str,
)
from app.modules.aas.serialization import aas_to_jsonld, aas_to_turtle, aas_to_xml

__all__ = [
    "AASValidationResult",
    "aas_to_jsonld",
    "aas_to_turtle",
    "aas_to_xml",
    "clear_parent",
    "clone_identifiable",
    "enum_to_str",
    "extract_semantic_id_str",
    "iterable_attr",
    "lang_string_set_to_dict",
    "reference_from_dict",
    "reference_to_dict",
    "reference_to_str",
    "validate_aas_environment",
    "walk_submodel_deep",
]
