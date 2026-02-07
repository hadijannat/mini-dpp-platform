"""Convert template definition AST into deterministic UI schema."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

VALUE_TYPE_TO_JSON: dict[str, str] = {
    "xs:string": "string",
    "xs:boolean": "boolean",
    "xs:integer": "integer",
    "xs:int": "integer",
    "xs:long": "integer",
    "xs:short": "integer",
    "xs:decimal": "number",
    "xs:double": "number",
    "xs:float": "number",
    "xs:date": "string",
    "xs:dateTime": "string",
    "xs:anyURI": "string",
}


class DefinitionToSchemaConverter:
    """Derive JSON schema from the canonical template definition AST."""

    def convert(self, definition: dict[str, Any]) -> dict[str, Any]:
        submodel = definition.get("submodel") or {}
        schema: dict[str, Any] = {
            "type": "object",
            "title": submodel.get("idShort") or "Submodel",
            "description": self._pick_text(submodel.get("description")),
            "properties": {},
            "required": [],
        }

        for node in self._sorted_nodes(submodel.get("elements") or []):
            key = node.get("idShort")
            if not key:
                continue
            schema["properties"][key] = self._node_to_schema(node)
            if self._is_required(node):
                schema["required"].append(key)

        return schema

    def _node_to_schema(self, node: dict[str, Any]) -> dict[str, Any]:
        model_type = node.get("modelType") or "Property"

        if model_type == "SubmodelElementCollection":
            schema = self._collection_schema(node)
        elif model_type == "SubmodelElementList":
            schema = self._list_schema(node)
        elif model_type == "Property":
            schema = self._property_schema(node)
        elif model_type == "MultiLanguageProperty":
            schema = self._multi_language_schema(node)
        elif model_type == "Range":
            schema = self._range_schema(node)
        elif model_type == "File":
            schema = self._file_schema(node)
        elif model_type == "Blob":
            schema = self._blob_schema(node)
        elif model_type == "ReferenceElement":
            schema = self._reference_schema(node)
        elif model_type == "Entity":
            schema = self._entity_schema(node)
        elif model_type == "RelationshipElement":
            schema = self._relationship_schema(node)
        elif model_type == "AnnotatedRelationshipElement":
            schema = self._annotated_relationship_schema(node)
        else:
            schema = {
                "type": "object",
                "title": node.get("idShort") or "",
                "description": self._pick_text(node.get("description")),
                "properties": {},
                "x-readonly": True,
            }

        return self._apply_smt(schema, node.get("smt") or {})

    def _collection_schema(self, node: dict[str, Any]) -> dict[str, Any]:
        schema: dict[str, Any] = {
            "type": "object",
            "title": node.get("idShort") or "",
            "description": self._pick_text(node.get("description")),
            "properties": {},
            "required": [],
        }
        for child in self._sorted_nodes(node.get("children") or []):
            child_key = child.get("idShort")
            if not child_key:
                continue
            schema["properties"][child_key] = self._node_to_schema(child)
            if self._is_required(child):
                schema["required"].append(child_key)
        return schema

    def _list_schema(self, node: dict[str, Any]) -> dict[str, Any]:
        item = node.get("items")
        items_schema: dict[str, Any]
        if isinstance(item, dict):
            items_schema = self._node_to_schema(item)
        else:
            # Synthesize item schema from list's type hints when no sample item exists
            type_hint = node.get("typeValueListElement")
            if type_hint == "SubmodelElementCollection":
                items_schema = {"type": "object", "properties": {}}
            elif type_hint in {
                "Property",
                "MultiLanguageProperty",
                "Range",
                "File",
                "Blob",
                "ReferenceElement",
                "Entity",
                "RelationshipElement",
                "AnnotatedRelationshipElement",
            }:
                synthetic_node: dict[str, Any] = {
                    "modelType": type_hint,
                    "valueType": node.get("valueTypeListElement") or "xs:string",
                }
                items_schema = self._node_to_schema(synthetic_node)
            else:
                items_schema = {"type": "string"}
        schema: dict[str, Any] = {
            "type": "array",
            "title": node.get("idShort") or "",
            "description": self._pick_text(node.get("description")),
            "items": items_schema,
        }
        cardinality = ((node.get("smt") or {}).get("cardinality") or "").strip()
        if cardinality == "OneToMany":
            schema["minItems"] = 1
        elif cardinality == "ZeroToMany":
            schema["minItems"] = 0
        return schema

    def _property_schema(self, node: dict[str, Any]) -> dict[str, Any]:
        value_type = node.get("valueType") or "xs:string"
        schema: dict[str, Any] = {
            "type": VALUE_TYPE_TO_JSON.get(value_type, "string"),
            "title": node.get("idShort") or "",
            "description": self._pick_text(node.get("description")),
        }
        if value_type in {"xs:date", "xs:dateTime"}:
            schema["format"] = "date-time" if value_type == "xs:dateTime" else "date"
        elif value_type == "xs:anyURI":
            schema["format"] = "uri"
        if node.get("semanticId"):
            schema["x-semantic-id"] = node["semanticId"]
        return schema

    def _multi_language_schema(self, node: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "object",
            "title": node.get("idShort") or "",
            "description": self._pick_text(node.get("description")),
            "additionalProperties": {"type": "string"},
            "x-multi-language": True,
        }

    def _range_schema(self, node: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "object",
            "title": node.get("idShort") or "",
            "description": self._pick_text(node.get("description")),
            "properties": {
                "min": {"type": "number"},
                "max": {"type": "number"},
            },
            "x-range": True,
        }

    def _file_schema(self, node: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "object",
            "title": node.get("idShort") or "",
            "description": self._pick_text(node.get("description")),
            "properties": {
                "contentType": {"type": "string"},
                "value": {"type": "string", "format": "uri"},
            },
            "x-file-upload": True,
        }

    def _blob_schema(self, node: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "object",
            "title": node.get("idShort") or "",
            "description": self._pick_text(node.get("description")),
            "properties": {
                "contentType": {"type": "string"},
                "value": {"type": "string", "contentEncoding": "base64"},
            },
            "x-blob": True,
            "x-readonly": True,
        }

    def _reference_schema(self, node: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "object",
            "title": node.get("idShort") or "",
            "description": self._pick_text(node.get("description")),
            "properties": {
                "type": {"type": "string", "enum": ["ModelReference", "ExternalReference"]},
                "keys": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "value": {"type": "string"},
                        },
                    },
                },
            },
            "x-reference": True,
        }

    def _entity_schema(self, node: dict[str, Any]) -> dict[str, Any]:
        statements_schema: dict[str, Any] = {
            "type": "object",
            "title": "Statements",
            "properties": {},
        }
        for statement in self._sorted_nodes(node.get("statements") or []):
            statement_key = statement.get("idShort")
            if statement_key:
                statements_schema["properties"][statement_key] = self._node_to_schema(statement)

        return {
            "type": "object",
            "title": node.get("idShort") or "",
            "description": self._pick_text(node.get("description")),
            "properties": {
                "entityType": {
                    "type": "string",
                    "enum": ["SelfManagedEntity", "CoManagedEntity"],
                },
                "globalAssetId": {"type": "string"},
                "statements": statements_schema,
            },
            "x-entity": True,
        }

    def _relationship_schema(self, node: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "object",
            "title": node.get("idShort") or "",
            "description": self._pick_text(node.get("description")),
            "properties": {
                "first": self._reference_schema({"idShort": "First"}),
                "second": self._reference_schema({"idShort": "Second"}),
            },
            "x-relationship": True,
        }

    def _annotated_relationship_schema(self, node: dict[str, Any]) -> dict[str, Any]:
        annotations_schema: dict[str, Any] = {
            "type": "object",
            "title": "Annotations",
            "properties": {},
        }
        for annotation in self._sorted_nodes(node.get("annotations") or []):
            annotation_key = annotation.get("idShort")
            if annotation_key:
                annotations_schema["properties"][annotation_key] = self._node_to_schema(annotation)

        return {
            "type": "object",
            "title": node.get("idShort") or "",
            "description": self._pick_text(node.get("description")),
            "properties": {
                "first": self._reference_schema({"idShort": "First"}),
                "second": self._reference_schema({"idShort": "Second"}),
                "annotations": annotations_schema,
            },
            "x-annotated-relationship": True,
        }

    def _apply_smt(self, schema: dict[str, Any], smt: dict[str, Any]) -> dict[str, Any]:
        cardinality = smt.get("cardinality")
        if cardinality:
            schema["x-cardinality"] = cardinality

        form_title = smt.get("form_title")
        if form_title:
            schema["title"] = form_title
            schema["x-form-title"] = form_title

        form_info = smt.get("form_info")
        if form_info:
            if not schema.get("description"):
                schema["description"] = form_info
            schema["x-form-info"] = form_info

        form_url = smt.get("form_url")
        if form_url:
            schema["x-form-url"] = form_url

        form_choices = smt.get("form_choices") or []
        if isinstance(form_choices, list) and form_choices:
            schema["x-form-choices"] = form_choices
            if schema.get("type") == "string" and not schema.get("enum"):
                schema["enum"] = form_choices

        default_value = smt.get("default_value")
        if default_value is not None and schema.get("type"):
            schema["default"] = self._coerce_value(default_value, schema["type"])

        example_value = smt.get("example_value")
        if example_value is not None and schema.get("type"):
            schema["examples"] = [self._coerce_value(example_value, schema["type"])]

        allowed_value_regex = smt.get("allowed_value_regex")
        if allowed_value_regex:
            schema["pattern"] = allowed_value_regex
            schema["x-allowed-value"] = allowed_value_regex

        allowed_range = smt.get("allowed_range")
        self._apply_allowed_range(schema, allowed_range)

        required_lang = smt.get("required_lang") or []
        if isinstance(required_lang, list) and required_lang:
            schema["x-required-languages"] = sorted({str(v) for v in required_lang})

        either_or = smt.get("either_or")
        if either_or:
            schema["x-either-or"] = either_or

        access_mode = (smt.get("access_mode") or "").strip().lower()
        if access_mode in {"readonly", "read-only", "read_only"}:
            schema["readOnly"] = True
            schema["x-readonly"] = True
        if access_mode in {"writeonly", "write-only", "write_only"}:
            schema["writeOnly"] = True

        allowed_id_short = smt.get("allowed_id_short") or []
        if isinstance(allowed_id_short, list) and allowed_id_short:
            schema["x-allowed-id-short"] = [str(v) for v in allowed_id_short]

        edit_id_short = smt.get("edit_id_short")
        if edit_id_short is not None:
            schema["x-edit-id-short"] = bool(edit_id_short)

        naming = smt.get("naming")
        if naming:
            schema["x-naming"] = naming

        return schema

    def _apply_allowed_range(self, schema: dict[str, Any], allowed_range: Any) -> None:
        if allowed_range is None:
            return

        if isinstance(allowed_range, dict):
            min_value = allowed_range.get("min")
            max_value = allowed_range.get("max")
            raw = allowed_range.get("raw")
            if isinstance(min_value, (int, float)):
                schema["minimum"] = float(min_value)
            if isinstance(max_value, (int, float)):
                schema["maximum"] = float(max_value)
            if raw and ("minimum" not in schema or "maximum" not in schema):
                schema["x-allowed-range"] = str(raw)
            return

        if isinstance(allowed_range, str):
            schema["x-allowed-range"] = allowed_range

    def _pick_text(self, value: Any) -> str:
        if isinstance(value, dict):
            if "en" in value:
                return str(value["en"])
            for _, item in sorted(value.items()):
                if item:
                    return str(item)
        if isinstance(value, str):
            return value
        return ""

    def _is_required(self, node: dict[str, Any]) -> bool:
        cardinality = ((node.get("smt") or {}).get("cardinality") or "").strip()
        return cardinality in {"One", "OneToMany"}

    def _sorted_nodes(self, nodes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        def key(node: dict[str, Any]) -> tuple[str, str, str]:
            return (
                str(node.get("idShort") or ""),
                str(node.get("path") or ""),
                str(node.get("modelType") or ""),
            )

        return sorted((node for node in nodes if isinstance(node, dict)), key=key)

    def _coerce_value(self, value: Any, json_type: str) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        if json_type == "integer":
            try:
                return int(value)
            except ValueError:
                return value
        if json_type == "number":
            try:
                return float(value)
            except ValueError:
                return value
        if json_type == "boolean":
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False
        return value
