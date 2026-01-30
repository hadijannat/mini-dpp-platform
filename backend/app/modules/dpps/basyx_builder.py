"""BaSyx-native DPP builder utilities."""

from __future__ import annotations

import copy
import io
import json
import re
from collections.abc import Iterable
from contextlib import suppress
from typing import Any, cast

from basyx.aas import model
from basyx.aas.adapter import json as basyx_json

from app.core.logging import get_logger
from app.modules.templates.basyx_parser import BasyxTemplateParser
from app.modules.templates.catalog import get_template_descriptor
from app.modules.templates.definition import TemplateDefinitionBuilder
from app.modules.templates.service import TemplateRegistryService

logger = get_logger(__name__)


class BasyxDppBuilder:
    """Build AAS environments using BaSyx model objects."""

    def __init__(self, template_service: TemplateRegistryService) -> None:
        self._template_service = template_service
        self._template_parser = BasyxTemplateParser()

    async def build_environment(
        self,
        asset_ids: dict[str, Any],
        selected_templates: list[str],
        initial_data: dict[str, Any],
    ) -> dict[str, Any]:
        store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()

        aas = self._build_aas(asset_ids)
        store.add(aas)

        for template_key in selected_templates:
            template = await self._template_service.get_template(template_key)
            if not template:
                try:
                    template = await self._template_service.refresh_template(template_key)
                except Exception as exc:
                    logger.warning(
                        "template_missing_and_refresh_failed",
                        template_key=template_key,
                        error=str(exc),
                    )
                    template = None

            if not template:
                logger.warning("template_not_found", template_key=template_key)
                continue

            descriptor = get_template_descriptor(template_key)
            if descriptor is None:
                logger.warning("template_descriptor_missing", template_key=template_key)
                continue

            parsed = self._parse_template(template, descriptor.semantic_id)
            submodel = self._instantiate_submodel(
                template_key,
                asset_ids,
                parsed.submodel,
                initial_data.get(template_key, {}),
            )

            store.add(submodel)
            for cd in parsed.concept_descriptions:
                with suppress(KeyError):
                    store.add(self._clone_identifiable(cd))

            aas.submodel.add(model.ModelReference.from_referable(submodel))

        env_json_str = basyx_json.object_store_to_json(store)  # type: ignore[attr-defined]
        return cast(dict[str, Any], json.loads(env_json_str))

    def update_submodel_environment(
        self,
        aas_env_json: dict[str, Any],
        template_key: str,
        template: Any,
        submodel_data: dict[str, Any],
        asset_ids: dict[str, Any],
        rebuild_from_template: bool,
    ) -> dict[str, Any]:
        descriptor = get_template_descriptor(template_key)
        if descriptor is None:
            raise ValueError(f"Unknown template key: {template_key}")

        store, aas = self._load_environment(aas_env_json)
        existing_submodel = self._find_submodel(store, descriptor.semantic_id)

        parsed = self._parse_template(template, descriptor.semantic_id)
        template_submodel = parsed.submodel

        if rebuild_from_template or existing_submodel is None:
            new_submodel = self._instantiate_submodel(
                template_key,
                asset_ids,
                template_submodel,
                submodel_data,
            )
            if existing_submodel is not None:
                new_submodel.id = existing_submodel.id
                store.discard(existing_submodel)
            store.add(new_submodel)
            if existing_submodel is None:
                aas.submodel.add(model.ModelReference.from_referable(new_submodel))
        else:
            updated_elements = [
                self._instantiate_element(element, submodel_data.get(element.id_short))
                for element in existing_submodel.submodel_element
            ]
            existing_submodel.submodel_element = cast(Any, updated_elements)

        for cd in parsed.concept_descriptions:
            with suppress(KeyError):
                store.add(self._clone_identifiable(cd))

        env_json_str = basyx_json.object_store_to_json(store)  # type: ignore[attr-defined]
        return cast(dict[str, Any], json.loads(env_json_str))

    def build_submodel_definition(
        self,
        aas_env_json: dict[str, Any],
        template_key: str | None,
        semantic_id: str,
        idta_version: str | None = None,
    ) -> dict[str, Any]:
        store, _ = self._load_environment(aas_env_json)
        submodel = self._find_submodel(store, semantic_id)
        if submodel is None:
            raise ValueError("Submodel not found in AAS environment")

        concept_desc_type = getattr(model, "ConceptDescription", None)
        concept_descriptions: list[Any] = []
        if concept_desc_type is not None:
            concept_descriptions = [obj for obj in store if isinstance(obj, concept_desc_type)]

        builder = TemplateDefinitionBuilder()
        return builder.build_submodel_definition(
            template_key=template_key,
            submodel=submodel,
            idta_version=idta_version,
            semantic_id=semantic_id,
            concept_descriptions=concept_descriptions,
        )

    def rebuild_environment_from_templates(
        self,
        aas_env_json: dict[str, Any],
        templates: list[Any],
        asset_ids: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        store, _ = self._load_environment(aas_env_json)
        submodels = [obj for obj in store if isinstance(obj, model.Submodel)]
        if not submodels:
            return aas_env_json, False

        changed = False

        for submodel in submodels:
            template = self._match_template_for_submodel(submodel, templates)
            if not template:
                continue
            template_key = template.template_key
            descriptor = get_template_descriptor(template_key)
            if descriptor is None:
                continue

            parsed = self._parse_template(template, descriptor.semantic_id)
            submodel_data = self._extract_submodel_data(submodel)
            new_submodel = self._instantiate_submodel(
                template_key,
                asset_ids,
                parsed.submodel,
                submodel_data,
            )
            new_submodel.id = submodel.id

            store.discard(submodel)
            store.add(new_submodel)
            for cd in parsed.concept_descriptions:
                with suppress(KeyError):
                    store.add(self._clone_identifiable(cd))

            changed = True

        if not changed:
            return aas_env_json, False

        env_json_str = basyx_json.object_store_to_json(store)  # type: ignore[attr-defined]
        return cast(dict[str, Any], json.loads(env_json_str)), True

    def _parse_template(self, template: Any, semantic_id: str) -> Any:
        if template.template_aasx:
            try:
                return self._template_parser.parse_aasx(
                    template.template_aasx,
                    expected_semantic_id=semantic_id,
                )
            except Exception as exc:
                logger.warning(
                    "template_aasx_parse_failed",
                    template_key=template.template_key,
                    version=template.idta_version,
                    error=str(exc),
                )

        payload = json.dumps(template.template_json).encode()
        return self._template_parser.parse_json(
            payload,
            expected_semantic_id=semantic_id,
        )

    def _load_environment(
        self, aas_env_json: dict[str, Any]
    ) -> tuple[model.DictObjectStore[model.Identifiable], model.AssetAdministrationShell]:
        try:
            payload = json.dumps(aas_env_json, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Failed to serialize AAS environment JSON: {exc}") from exc

        string_io = io.StringIO(payload)
        try:
            store = basyx_json.read_aas_json_file(  # type: ignore[attr-defined]
                string_io
            )
        except Exception as exc:
            raise ValueError(f"Failed to parse AAS environment: {exc}") from exc
        finally:
            string_io.close()

        aas = next((obj for obj in store if isinstance(obj, model.AssetAdministrationShell)), None)
        if aas is None:
            raise ValueError("AAS environment missing AssetAdministrationShell")
        return store, aas

    def _find_submodel(
        self,
        store: model.DictObjectStore[model.Identifiable],
        semantic_id: str,
    ) -> model.Submodel | None:
        for obj in store:
            if not isinstance(obj, model.Submodel):
                continue
            candidate = self._reference_to_str(obj.semantic_id)
            if candidate and semantic_id in candidate:
                return obj
        return None

    def _match_template_for_submodel(
        self, submodel: model.Submodel, templates: list[Any]
    ) -> Any | None:
        submodel_semantic = self._reference_to_str(submodel.semantic_id) or ""
        for template in templates:
            if template.semantic_id and template.semantic_id in submodel_semantic:
                return template
        return None

    def _build_aas(self, asset_ids: dict[str, Any]) -> model.AssetAdministrationShell:
        aas_id = f"urn:dpp:aas:{asset_ids.get('manufacturerPartId', 'unknown')}"

        raw_part_id = str(asset_ids.get("manufacturerPartId", "Product"))
        safe_part_id = self._sanitize_id_short(raw_part_id)

        specific_asset_ids = [
            model.SpecificAssetId(name=key, value=str(value))
            for key, value in asset_ids.items()
            if key != "globalAssetId"
        ]

        asset_information = model.AssetInformation(
            asset_kind=model.AssetKind.INSTANCE,
            global_asset_id=asset_ids.get("globalAssetId", aas_id),
            specific_asset_id=specific_asset_ids,
        )

        return model.AssetAdministrationShell(
            asset_information=asset_information,
            id_=aas_id,
            id_short=f"DPP_{safe_part_id}",
            submodel=set(),
        )

    def _sanitize_id_short(self, value: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9_]", "_", value.strip())
        if not normalized:
            return "DPP"
        if normalized[0].isdigit():
            return f"_{normalized}"
        return normalized

    def _instantiate_submodel(
        self,
        template_key: str,
        asset_ids: dict[str, Any],
        template_submodel: model.Submodel,
        initial_values: dict[str, Any],
    ) -> model.Submodel:
        submodel_id = f"urn:dpp:sm:{template_key}:{asset_ids.get('manufacturerPartId', 'unknown')}"

        elements = [
            self._instantiate_element(element, initial_values.get(element.id_short))
            for element in template_submodel.submodel_element
        ]

        return model.Submodel(
            id_=submodel_id,
            id_short=template_submodel.id_short,
            display_name=template_submodel.display_name,
            category=template_submodel.category,
            description=template_submodel.description,
            administration=template_submodel.administration,
            semantic_id=template_submodel.semantic_id,
            qualifier=template_submodel.qualifier,
            kind=model.ModellingKind.INSTANCE,
            extension=template_submodel.extension,
            supplemental_semantic_id=template_submodel.supplemental_semantic_id,
            embedded_data_specifications=template_submodel.embedded_data_specifications,
            submodel_element=elements,
        )

    def _instantiate_element(
        self,
        template_element: model.SubmodelElement,
        value: Any,
    ) -> model.SubmodelElement:
        element = copy.deepcopy(template_element)
        self._clear_parent(element)
        element_value = value

        if isinstance(element, model.Property):
            element.value = self._coerce_property_value(
                element_value,
                element.value_type,
                element.value,
            )
        elif isinstance(element, model.MultiLanguageProperty):
            if isinstance(element_value, dict):
                element.value = cast(Any, model.LangStringSet(element_value))
        elif isinstance(element, model.Range):
            if isinstance(element_value, dict):
                element.min = element_value.get("min")
                element.max = element_value.get("max")
        elif isinstance(element, (model.File, model.Blob)):
            if isinstance(element_value, dict):
                element.content_type = element_value.get("contentType", element.content_type)
                raw_value = element_value.get("value")
                if raw_value in ("", None):
                    element.value = None
                else:
                    element.value = raw_value
        elif isinstance(element, model.SubmodelElementCollection):
            if isinstance(element_value, dict):
                element.value = cast(Any, self._hydrate_children(element.value, element_value))
        elif isinstance(element, model.SubmodelElementList):
            if isinstance(element_value, list):
                element.value = cast(Any, self._hydrate_list_items(element, element_value))
        elif isinstance(element, model.ReferenceElement):
            if isinstance(element_value, dict):
                reference = self._reference_from_dict(element_value)
                if reference is not None:
                    element.value = reference
        elif isinstance(element, model.RelationshipElement):
            if isinstance(element_value, dict):
                first = self._reference_from_dict(element_value.get("first"))
                second = self._reference_from_dict(element_value.get("second"))
                if first is not None:
                    element.first = first
                if second is not None:
                    element.second = second
        elif isinstance(element, model.AnnotatedRelationshipElement):
            if isinstance(element_value, dict):
                first = self._reference_from_dict(element_value.get("first"))
                second = self._reference_from_dict(element_value.get("second"))
                if first is not None:
                    element.first = first
                if second is not None:
                    element.second = second
                annotations = element.annotation
                annotation_values = element_value.get("annotations", {})
                if isinstance(annotation_values, dict):
                    element.annotation = cast(
                        Any, self._hydrate_children(annotations, annotation_values)
                    )
        elif isinstance(element, model.Entity) and isinstance(element_value, dict):
            if element_value.get("globalAssetId") is not None:
                element.global_asset_id = element_value.get("globalAssetId")
            statements = element.statement
            statement_values = element_value.get("statements", {})
            if isinstance(statement_values, dict):
                element.statement = cast(Any, self._hydrate_children(statements, statement_values))

        return element

    def _extract_submodel_data(self, submodel: model.Submodel) -> dict[str, Any]:
        return self._extract_elements(submodel.submodel_element)

    def _extract_elements(self, elements: Iterable[model.SubmodelElement]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for element in elements:
            if not element.id_short:
                continue
            data[element.id_short] = self._extract_element_value(element)
        return data

    def _extract_element_value(self, element: model.SubmodelElement) -> Any:
        if isinstance(element, model.SubmodelElementCollection):
            return self._extract_elements(element.value)
        if isinstance(element, model.SubmodelElementList):
            return [self._extract_element_value(item) for item in element.value]
        if isinstance(element, model.MultiLanguageProperty):
            try:
                return dict(element.value or {})
            except TypeError:
                return {}
        if isinstance(element, model.Range):
            return {"min": element.min, "max": element.max}
        if isinstance(element, model.File):
            return {"contentType": element.content_type, "value": element.value}
        if isinstance(element, model.Blob):
            return {"contentType": element.content_type, "value": element.value}
        if isinstance(element, model.ReferenceElement):
            return self._reference_to_dict(element.value)
        if isinstance(element, model.Entity):
            return {
                "entityType": element.entity_type.name
                if hasattr(element.entity_type, "name")
                else str(element.entity_type),
                "globalAssetId": element.global_asset_id,
                "statements": self._extract_elements(element.statement),
            }
        if isinstance(element, model.RelationshipElement):
            return {
                "first": self._reference_to_dict(element.first),
                "second": self._reference_to_dict(element.second),
            }
        if isinstance(element, model.AnnotatedRelationshipElement):
            return {
                "first": self._reference_to_dict(element.first),
                "second": self._reference_to_dict(element.second),
                "annotations": self._extract_elements(element.annotation),
            }
        if isinstance(element, model.Property):
            return element.value
        return getattr(element, "value", None)

    def _hydrate_children(
        self,
        children: Iterable[model.SubmodelElement],
        values: dict[str, Any],
    ) -> list[model.SubmodelElement]:
        hydrated: list[model.SubmodelElement] = []
        for child in children:
            child_value = values.get(child.id_short)
            hydrated.append(self._instantiate_element(child, child_value))
        return hydrated

    def _hydrate_list_items(
        self,
        element: Any,
        values: list[Any],
    ) -> list[model.SubmodelElement]:
        items: list[model.SubmodelElement] = []
        template_item = element.value[0] if element.value else None

        for value in values:
            if template_item is not None:
                new_item = self._instantiate_element(template_item, value)
                self._strip_list_item_id_short(new_item)
                items.append(new_item)
                continue

            item_type = element.type_value_list_element
            if item_type is None:
                continue

            items.append(self._instantiate_list_item_from_type(item_type, element, value))

        return items

    def _instantiate_list_item_from_type(
        self,
        item_type: type[model.SubmodelElement],
        list_element: Any,
        value: Any,
    ) -> model.SubmodelElement:
        if item_type is model.Property:
            value_type = list_element.value_type_list_element or str
            instance: model.SubmodelElement = model.Property(
                id_short=None,
                value_type=value_type,
                value=self._coerce_property_value(value, value_type, None),
            )
            self._clear_parent(instance)
            return instance
        if item_type is model.MultiLanguageProperty and isinstance(value, dict):
            instance = model.MultiLanguageProperty(
                id_short=None,
                value=cast(Any, model.LangStringSet(value)),
            )
            self._clear_parent(instance)
            return instance
        if item_type is model.SubmodelElementCollection and isinstance(value, dict):
            instance = model.SubmodelElementCollection(
                id_short=None,
                value=[
                    self._instantiate_element(child, value.get(child.id_short))
                    for child in list_element.value
                ],
            )
            self._clear_parent(instance)
            return instance

        instance = item_type(id_short=None)
        self._clear_parent(instance)
        return instance

    def _strip_list_item_id_short(self, element: model.SubmodelElement) -> None:
        if hasattr(element, "id_short"):
            element.id_short = None

    def _clone_identifiable(self, identifiable: model.Identifiable) -> model.Identifiable:
        cloned = copy.deepcopy(identifiable)
        if hasattr(cloned, "parent"):
            cloned.parent = None
        return cloned

    def _clear_parent(self, element: model.SubmodelElement) -> None:
        if hasattr(element, "parent"):
            element.parent = None

        if isinstance(element, (model.SubmodelElementCollection, model.SubmodelElementList)):
            for child in element.value:
                self._clear_parent(child)
        elif isinstance(element, model.AnnotatedRelationshipElement):
            for child in element.annotation:
                self._clear_parent(child)
        elif isinstance(element, model.Entity):
            for child in element.statement:
                self._clear_parent(child)

    def _reference_from_dict(self, payload: Any) -> model.Reference | None:
        if not isinstance(payload, dict):
            return None
        keys = payload.get("keys")
        if not isinstance(keys, list):
            return None
        key_objs: list[model.Key] = []
        for entry in keys:
            if not isinstance(entry, dict):
                continue
            key_type_value = str(entry.get("type", "")).upper().replace(" ", "_")
            if not key_type_value:
                continue
            try:
                key_type = model.KeyTypes[key_type_value]
            except KeyError:
                continue
            key_value = str(entry.get("value", ""))
            key_objs.append(model.Key(key_type, key_value))
        if not key_objs:
            return None
        reference_type = str(payload.get("type", "")).lower()
        if reference_type == "modelreference":
            # ModelReference requires a concrete referred type; fall back to external reference.
            return model.ExternalReference(tuple(key_objs))
        return model.ExternalReference(tuple(key_objs))

    def _coerce_property_value(self, value: Any, value_type: Any, fallback: Any) -> Any:
        if value is None:
            return fallback
        if value_type in (int, float, bool, str):
            try:
                return value_type(value)
            except (TypeError, ValueError):
                return value
        return value

    def _reference_to_str(self, reference: model.Reference | None) -> str | None:
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
                "type": key.type.name if hasattr(key.type, "name") else str(key.type),
                "value": key.value,
            }
            for key in keys
        ]
        return {
            "type": reference.__class__.__name__,
            "keys": key_dicts,
        }
