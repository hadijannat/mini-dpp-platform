"""Template definition builder using BaSyx object model."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from basyx.aas import model

from app.modules.aas.model_utils import enum_to_str, iterable_attr, lang_string_set_to_dict
from app.modules.aas.references import reference_to_dict, reference_to_str
from app.modules.templates.basyx_parser import ParsedTemplate
from app.modules.templates.qualifiers import parse_smt_qualifiers

logger = logging.getLogger(__name__)


class TemplateDefinitionBuilder:
    """Build a stable, UI-friendly definition AST from a parsed template."""

    def __init__(
        self,
        resolution_by_element_id: Mapping[int, dict[str, Any]] | None = None,
        uom_by_cd_id: Mapping[str, dict[str, Any]] | None = None,
        validation_by_cd_id: Mapping[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self._resolution_by_element_id = dict(resolution_by_element_id or {})
        self._uom_by_cd_id = dict(uom_by_cd_id or {})
        self._validation_by_cd_id = {
            key: list(value) for key, value in (validation_by_cd_id or {}).items()
        }

    def build_definition(
        self,
        template_key: str,
        parsed: ParsedTemplate,
        idta_version: str | None = None,
        semantic_id: str | None = None,
    ) -> dict[str, Any]:
        submodel = parsed.submodel
        definition: dict[str, Any] = {
            "template_key": template_key,
            "idta_version": idta_version,
            "semantic_id": semantic_id or reference_to_str(submodel.semantic_id),
            "submodel": self._submodel_definition(submodel),
        }
        if parsed.concept_descriptions:
            definition["concept_descriptions"] = [
                self._concept_description_definition(cd) for cd in parsed.concept_descriptions
            ]
        return definition

    def build_submodel_definition(
        self,
        template_key: str | None,
        submodel: model.Submodel,
        idta_version: str | None = None,
        semantic_id: str | None = None,
        concept_descriptions: list[Any] | None = None,
    ) -> dict[str, Any]:
        definition: dict[str, Any] = {
            "template_key": template_key,
            "idta_version": idta_version,
            "semantic_id": semantic_id or reference_to_str(submodel.semantic_id),
            "submodel": self._submodel_definition(submodel),
        }
        if concept_descriptions:
            definition["concept_descriptions"] = [
                self._concept_description_definition(cd) for cd in concept_descriptions
            ]
        return definition

    def _submodel_definition(self, submodel: model.Submodel) -> dict[str, Any]:
        qualifiers = self._qualifiers_to_dicts(submodel)
        elements = self._ordered_elements(
            iterable_attr(submodel, "submodel_element", "submodel_elements")
        )
        node = {
            "id": submodel.id,
            "idShort": submodel.id_short,
            "kind": enum_to_str(getattr(submodel, "kind", None)),
            "semanticId": reference_to_str(submodel.semantic_id),
            "displayName": lang_string_set_to_dict(submodel.display_name),
            "description": lang_string_set_to_dict(submodel.description),
            "qualifiers": qualifiers,
            "smt": asdict(parse_smt_qualifiers(qualifiers)),
            "elements": [
                self._element_definition(element, parent_path=submodel.id_short, order=index)
                for index, element in enumerate(elements)
            ],
        }
        supplemental_ids = self._supplemental_semantic_ids(submodel)
        if supplemental_ids:
            node["supplementalSemanticIds"] = supplemental_ids
        return node

    def _element_definition(
        self,
        element: model.SubmodelElement,
        parent_path: str,
        order: int | None = None,
    ) -> dict[str, Any]:
        model_type = element.__class__.__name__
        raw_id_short = getattr(element, "id_short", None)
        id_short = self._normalize_id_short(raw_id_short)
        if id_short:
            path = f"{parent_path}/{id_short}" if parent_path else id_short
        else:
            path = parent_path or ""
        qualifiers = self._qualifiers_to_dicts(element)

        node: dict[str, Any] = {
            "path": path,
            "idShort": id_short,
            "modelType": model_type,
            "semanticId": reference_to_str(element.semantic_id),
            "displayName": lang_string_set_to_dict(element.display_name),
            "description": lang_string_set_to_dict(element.description),
            "qualifiers": qualifiers,
            "smt": asdict(parse_smt_qualifiers(qualifiers)),
        }
        if order is not None:
            node["order"] = order

        supplemental_ids = self._supplemental_semantic_ids(element)
        if supplemental_ids:
            node["supplementalSemanticIds"] = supplemental_ids

        if isinstance(element, model.Property):
            node["valueType"] = enum_to_str(element.value_type)
        elif isinstance(element, model.MultiLanguageProperty):
            node["valueType"] = "langStringSet"
        elif isinstance(element, model.Range):
            node["valueType"] = enum_to_str(element.value_type)
        elif isinstance(element, (model.File, model.Blob)):
            node["contentType"] = element.content_type
        elif isinstance(element, model.SubmodelElementCollection):
            children = self._ordered_elements(
                iterable_attr(element, "value", "submodel_element", "submodel_elements")
            )
            node["children"] = [
                self._element_definition(child, parent_path=path, order=index)
                for index, child in enumerate(children)
            ]
        elif isinstance(element, model.SubmodelElementList):
            node["orderRelevant"] = element.order_relevant
            node["typeValueListElement"] = enum_to_str(element.type_value_list_element)
            node["valueTypeListElement"] = enum_to_str(element.value_type_list_element)
            node["items"] = self._list_item_definition(element, path)
        elif isinstance(element, model.Entity):
            node["entityType"] = enum_to_str(element.entity_type)
            statements = self._ordered_elements(iterable_attr(element, "statement", "statements"))
            statement_path = f"{path}/statements" if path else "statements"
            node["statements"] = [
                self._element_definition(child, parent_path=statement_path, order=index)
                for index, child in enumerate(statements)
            ]
        elif isinstance(element, model.ReferenceElement):
            node["valueType"] = "reference"
        elif isinstance(element, model.AnnotatedRelationshipElement):
            # Must check before RelationshipElement (subclass of it)
            node["first"] = reference_to_str(getattr(element, "first", None))
            node["second"] = reference_to_str(getattr(element, "second", None))
            annotations = self._ordered_elements(
                iterable_attr(element, "annotation", "annotations")
            )
            annotation_path = f"{path}/annotations" if path else "annotations"
            node["annotations"] = [
                self._element_definition(child, parent_path=annotation_path, order=index)
                for index, child in enumerate(annotations)
            ]
        elif isinstance(element, model.RelationshipElement):
            node["first"] = reference_to_str(getattr(element, "first", None))
            node["second"] = reference_to_str(getattr(element, "second", None))
        elif isinstance(element, model.Operation):
            for var_kind in ("input_variable", "output_variable", "in_output_variable"):
                variables = getattr(element, var_kind, None)
                if variables:
                    var_path = f"{path}/{var_kind}" if path else var_kind
                    node[var_kind] = [
                        self._element_definition(v, parent_path=var_path, order=index)
                        for index, v in enumerate(self._ordered_elements(variables))
                    ]
        elif isinstance(element, model.Capability):
            pass  # Capability has no additional structural fields
        elif isinstance(element, model.BasicEventElement):
            node["observed"] = reference_to_str(getattr(element, "observed", None))
            node["direction"] = enum_to_str(getattr(element, "direction", None))
            node["state"] = enum_to_str(getattr(element, "state", None))

        resolution = self._resolution_by_element_id.get(id(element))
        if resolution:
            node["x_resolution"] = self._sorted_dict(resolution)

        return node

    def _list_item_definition(self, element: Any, parent_path: str) -> dict[str, Any] | None:
        items = self._ordered_elements(
            iterable_attr(element, "value", "submodel_element", "submodel_elements")
        )
        if items:
            return self._element_definition(items[0], parent_path=f"{parent_path}[]", order=0)
        if element.type_value_list_element:
            return {
                "path": f"{parent_path}[]",
                "modelType": enum_to_str(element.type_value_list_element),
                "valueType": enum_to_str(element.value_type_list_element),
                "order": 0,
            }
        return None

    def _concept_description_definition(self, cd: Any) -> dict[str, Any]:
        # Try structured IEC 61360 data specification first
        iec61360 = self._extract_iec61360(cd)
        if iec61360 is not None:
            payload = {
                "id": cd.id,
                "idShort": cd.id_short,
                "definition": lang_string_set_to_dict(iec61360.definition),
                "preferredName": lang_string_set_to_dict(iec61360.preferred_name),
                "shortName": lang_string_set_to_dict(getattr(iec61360, "short_name", None)),
                "unit": iec61360.unit,
                "unitId": reference_to_str(getattr(iec61360, "unit_id", None)),
                "dataType": enum_to_str(getattr(iec61360, "data_type", None)),
                "valueFormat": getattr(iec61360, "value_format", None),
            }
            return self._decorate_concept_description(payload)

        # Fallback: extract from top-level attributes (pre-IEC 61360 or custom CDs)
        definition_value = getattr(cd, "definition", None)
        if definition_value is None:
            definition_value = getattr(cd, "description", None)
        preferred_name_value = getattr(cd, "preferred_name", None)
        if preferred_name_value is None:
            preferred_name_value = getattr(cd, "display_name", None)
        short_name_value = getattr(cd, "short_name", None)
        if short_name_value is None:
            short_name_value = getattr(cd, "id_short", None)
        payload = {
            "id": cd.id,
            "idShort": cd.id_short,
            "definition": lang_string_set_to_dict(definition_value),
            "preferredName": lang_string_set_to_dict(preferred_name_value),
            "shortName": lang_string_set_to_dict(short_name_value),
            "unit": getattr(cd, "unit", None),
            "unitId": reference_to_str(getattr(cd, "unit_id", None)),
        }
        return self._decorate_concept_description(payload)

    @staticmethod
    def _extract_iec61360(cd: Any) -> Any | None:
        """Extract DataSpecificationIEC61360 from a ConceptDescription, if present."""
        eds_list = getattr(cd, "embedded_data_specifications", None)
        if not eds_list:
            return None
        for eds in eds_list:
            content = getattr(eds, "data_specification_content", None)
            if content is not None and type(content).__name__ == "DataSpecificationIEC61360":
                return content
        return None

    def _decorate_concept_description(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload.setdefault("kind", "concept")
        cd_id = str(payload.get("id") or "").strip()
        if not cd_id:
            return payload

        uom = self._uom_by_cd_id.get(cd_id)
        if isinstance(uom, dict):
            payload["kind"] = "unit"
            payload["uom"] = self._sorted_dict(uom)
            payload["unitResolutionStatus"] = "resolved"
        elif payload.get("unitId"):
            payload["unitResolutionStatus"] = "unresolved"

        validations = self._validation_by_cd_id.get(cd_id)
        if validations:
            payload["x_validation"] = [
                self._sorted_dict(item) if isinstance(item, dict) else item for item in validations
            ]

        return payload

    def _normalize_id_short(self, value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith("generated_submodel_list_hack_"):
            logger.debug("stripped_generated_id_short: %s", value)
            return None
        return value

    def _qualifiers_to_dicts(self, element: Any) -> list[dict[str, Any]]:
        qualifiers = getattr(element, "qualifier", None)
        if qualifiers is None:
            qualifiers = getattr(element, "qualifiers", None)
        if not qualifiers:
            return []
        qualifier_dicts = [self._qualifier_to_dict(q) for q in qualifiers]

        def sort_key(item: dict[str, Any]) -> tuple[str, str, str]:
            semantic = item.get("semanticId")
            semantic_key = (
                json.dumps(semantic, sort_keys=True, ensure_ascii=False) if semantic else ""
            )
            return (
                str(item.get("type") or ""),
                str(item.get("value") or ""),
                semantic_key,
            )

        qualifier_dicts.sort(key=sort_key)
        return qualifier_dicts

    def _qualifier_to_dict(self, qualifier: model.Qualifier) -> dict[str, Any]:
        return {
            "type": getattr(qualifier, "type", None),
            "value": getattr(qualifier, "value", None),
            "semanticId": reference_to_dict(getattr(qualifier, "semantic_id", None)),
        }

    def _ordered_elements(self, elements: Any) -> list[Any]:
        return list(elements or [])

    def _supplemental_semantic_ids(self, referable: Any) -> list[str]:
        refs = iterable_attr(referable, "supplemental_semantic_id", "supplemental_semantic_ids")
        values = [
            value
            for value in (reference_to_str(ref) for ref in refs)
            if isinstance(value, str) and value.strip()
        ]
        deduped = sorted({value.strip() for value in values})
        return deduped

    def _sorted_dict(self, payload: dict[str, Any]) -> dict[str, Any]:
        sorted_payload: dict[str, Any] = {}
        for key in sorted(payload.keys()):
            value = payload[key]
            if isinstance(value, dict):
                sorted_payload[key] = self._sorted_dict(value)
            elif isinstance(value, list):
                sorted_payload[key] = [
                    self._sorted_dict(item) if isinstance(item, dict) else item for item in value
                ]
            else:
                sorted_payload[key] = value
        return sorted_payload
