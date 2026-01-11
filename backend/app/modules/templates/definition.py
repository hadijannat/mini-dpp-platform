"""Template definition builder using BaSyx object model."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from basyx.aas import model

from app.modules.templates.basyx_parser import ParsedTemplate
from app.modules.templates.qualifiers import parse_smt_qualifiers


class TemplateDefinitionBuilder:
    """Build a stable, UI-friendly definition AST from a parsed template."""

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
            "semantic_id": semantic_id or self._reference_to_str(submodel.semantic_id),
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
            "semantic_id": semantic_id or self._reference_to_str(submodel.semantic_id),
            "submodel": self._submodel_definition(submodel),
        }
        if concept_descriptions:
            definition["concept_descriptions"] = [
                self._concept_description_definition(cd) for cd in concept_descriptions
            ]
        return definition

    def _submodel_definition(self, submodel: model.Submodel) -> dict[str, Any]:
        qualifiers = self._qualifiers_to_dicts(submodel)
        elements = self._iterable_attr(submodel, "submodel_element", "submodel_elements")
        return {
            "id": submodel.id,
            "idShort": submodel.id_short,
            "kind": self._enum_to_str(getattr(submodel, "kind", None)),
            "semanticId": self._reference_to_str(submodel.semantic_id),
            "displayName": self._lang_string_set(submodel.display_name),
            "description": self._lang_string_set(submodel.description),
            "qualifiers": qualifiers,
            "smt": asdict(parse_smt_qualifiers(qualifiers)),
            "elements": [
                self._element_definition(element, parent_path=submodel.id_short)
                for element in elements
            ],
        }

    def _element_definition(
        self,
        element: model.SubmodelElement,
        parent_path: str,
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
            "semanticId": self._reference_to_str(element.semantic_id),
            "displayName": self._lang_string_set(element.display_name),
            "description": self._lang_string_set(element.description),
            "qualifiers": qualifiers,
            "smt": asdict(parse_smt_qualifiers(qualifiers)),
        }

        if isinstance(element, model.Property):
            node["valueType"] = self._enum_to_str(element.value_type)
        elif isinstance(element, model.MultiLanguageProperty):
            node["valueType"] = "langStringSet"
        elif isinstance(element, model.Range):
            node["valueType"] = self._enum_to_str(element.value_type)
        elif isinstance(element, (model.File, model.Blob)):
            node["contentType"] = element.content_type
        elif isinstance(element, model.SubmodelElementCollection):
            children = self._iterable_attr(
                element, "value", "submodel_element", "submodel_elements"
            )
            node["children"] = [
                self._element_definition(child, parent_path=path) for child in children
            ]
        elif isinstance(element, model.SubmodelElementList):
            node["orderRelevant"] = element.order_relevant
            node["typeValueListElement"] = self._enum_to_str(element.type_value_list_element)
            node["valueTypeListElement"] = self._enum_to_str(element.value_type_list_element)
            node["items"] = self._list_item_definition(element, path)
        elif isinstance(element, model.Entity):
            node["entityType"] = self._enum_to_str(element.entity_type)
            statements = self._iterable_attr(element, "statement", "statements")
            statement_path = f"{path}/statements" if path else "statements"
            node["statements"] = [
                self._element_definition(child, parent_path=statement_path) for child in statements
            ]
        elif isinstance(element, model.AnnotatedRelationshipElement):
            annotations = self._iterable_attr(element, "annotation", "annotations")
            annotation_path = f"{path}/annotations" if path else "annotations"
            node["annotations"] = [
                self._element_definition(child, parent_path=annotation_path)
                for child in annotations
            ]

        return node

    def _list_item_definition(self, element: Any, parent_path: str) -> dict[str, Any] | None:
        items = self._iterable_attr(element, "value", "submodel_element", "submodel_elements")
        if items:
            return self._element_definition(items[0], parent_path=f"{parent_path}[]")
        if element.type_value_list_element:
            return {
                "path": f"{parent_path}[]",
                "modelType": self._enum_to_str(element.type_value_list_element),
                "valueType": self._enum_to_str(element.value_type_list_element),
            }
        return None

    def _concept_description_definition(self, cd: Any) -> dict[str, Any]:
        definition_value = getattr(cd, "definition", None)
        if definition_value is None:
            definition_value = getattr(cd, "description", None)
        preferred_name_value = getattr(cd, "preferred_name", None)
        if preferred_name_value is None:
            preferred_name_value = getattr(cd, "display_name", None)
        short_name_value = getattr(cd, "short_name", None)
        if short_name_value is None:
            short_name_value = getattr(cd, "id_short", None)
        return {
            "id": cd.id,
            "idShort": cd.id_short,
            "definition": self._lang_string_set(definition_value),
            "preferredName": self._lang_string_set(preferred_name_value),
            "shortName": self._lang_string_set(short_name_value),
            "unit": getattr(cd, "unit", None),
            "unitId": self._reference_to_str(getattr(cd, "unit_id", None)),
        }

    def _normalize_id_short(self, value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith("generated_submodel_list_hack_"):
            return None
        return value

    def _lang_string_set(self, value: Any) -> dict[str, str]:
        if not value:
            return {}
        if isinstance(value, str):
            return {"und": value}
        if hasattr(value, "language") and hasattr(value, "text"):
            language = getattr(value, "language", None)
            text = getattr(value, "text", None)
            if language is not None and text is not None:
                return {str(language): str(text)}
        result: dict[str, str] = {}
        for entry in value:
            language = getattr(entry, "language", None)
            text = getattr(entry, "text", None)
            if language is not None and text is not None:
                result[str(language)] = str(text)
        return result

    def _qualifiers_to_dicts(self, element: Any) -> list[dict[str, Any]]:
        qualifiers = getattr(element, "qualifier", None)
        if qualifiers is None:
            qualifiers = getattr(element, "qualifiers", None)
        if not qualifiers:
            return []
        return [self._qualifier_to_dict(q) for q in qualifiers]

    def _qualifier_to_dict(self, qualifier: model.Qualifier) -> dict[str, Any]:
        return {
            "type": getattr(qualifier, "type", None),
            "value": getattr(qualifier, "value", None),
            "semanticId": self._reference_to_dict(getattr(qualifier, "semantic_id", None)),
        }

    def _reference_to_str(self, reference: model.Reference | None) -> str | None:
        if reference is None:
            return None
        keys = getattr(reference, "keys", None)
        if keys is None:
            keys = getattr(reference, "key", None)
        if not keys:
            return None
        first = list(keys)[0]
        value = getattr(first, "value", None)
        return str(value) if value is not None else None

    def _reference_to_dict(self, reference: model.Reference | None) -> dict[str, Any] | None:
        if reference is None:
            return None
        keys = getattr(reference, "keys", None)
        if keys is None:
            keys = getattr(reference, "key", None)
        if not keys:
            return None
        key_dicts = [
            {
                "type": self._enum_to_str(getattr(key, "type", None)),
                "value": getattr(key, "value", None),
            }
            for key in keys
        ]
        return {
            "type": self._enum_to_str(getattr(reference, "type", None)),
            "keys": key_dicts,
        }

    def _enum_to_str(self, value: Any) -> str | None:
        if value is None:
            return None
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)

    def _iterable_attr(self, obj: Any, *names: str) -> list[Any]:
        for name in names:
            value = getattr(obj, name, None)
            if value is not None:
                return list(value)
        return []
