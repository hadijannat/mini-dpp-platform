"""Semantic-registry-driven template drop-in expansion."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from basyx.aas import model

from app.modules.aas.model_utils import detach_from_namespace, iterable_attr
from app.modules.aas.references import reference_to_str
from app.modules.semantic_registry import get_dropin_bindings_for_semantic_id

SourceSubmodelProvider = Callable[[str], model.Submodel | None]


class TemplateDropInResolver:
    """Resolve and inline unresolved drop-in placeholders in template submodels."""

    def resolve(
        self,
        *,
        template_key: str,
        submodel: model.Submodel,
        source_provider: SourceSubmodelProvider,
    ) -> dict[int, dict[str, Any]]:
        resolution_by_element_id: dict[int, dict[str, Any]] = {}
        source_indexes: dict[str, list[tuple[str, model.SubmodelElement]]] = {}

        for path, element in self._walk_elements(submodel):
            target_semantic_id = reference_to_str(getattr(element, "semantic_id", None))
            if not target_semantic_id:
                continue

            bindings = get_dropin_bindings_for_semantic_id(target_semantic_id)
            if not bindings:
                continue

            resolution = self._resolve_element(
                template_key=template_key,
                path=path,
                element=element,
                target_semantic_id=target_semantic_id,
                bindings=bindings,
                source_provider=source_provider,
                source_indexes=source_indexes,
            )
            if resolution is not None:
                resolution_by_element_id[id(element)] = resolution

        return resolution_by_element_id

    def _resolve_element(
        self,
        *,
        template_key: str,
        path: str,
        element: model.SubmodelElement,
        target_semantic_id: str,
        bindings: tuple[dict[str, Any], ...],
        source_provider: SourceSubmodelProvider,
        source_indexes: dict[str, list[tuple[str, model.SubmodelElement]]],
    ) -> dict[str, Any] | None:
        candidates = [
            binding
            for binding in bindings
            if self._binding_applies(
                binding=binding,
                template_key=template_key,
                model_type=type(element).__name__,
            )
        ]
        if not candidates:
            return None

        if not self._is_structurally_unresolved(element):
            binding = candidates[0]
            return self._resolution_payload(
                status="skipped",
                reason="target_already_structured",
                binding=binding,
                path=path,
                target_semantic_id=target_semantic_id,
            )

        first_failure: dict[str, Any] | None = None

        for binding in candidates:
            source_template_key = str(binding.get("source_template_key") or "").strip()
            if not source_template_key:
                failure = self._resolution_payload(
                    status="unresolved",
                    reason="missing_source_template_key",
                    binding=binding,
                    path=path,
                    target_semantic_id=target_semantic_id,
                )
                if first_failure is None:
                    first_failure = failure
                continue

            source_submodel = source_provider(source_template_key)
            if source_submodel is None:
                failure = self._resolution_payload(
                    status="unresolved",
                    reason="source_template_unavailable",
                    binding=binding,
                    path=path,
                    target_semantic_id=target_semantic_id,
                )
                if first_failure is None:
                    first_failure = failure
                continue

            if source_template_key not in source_indexes:
                source_indexes[source_template_key] = list(self._walk_elements(source_submodel))

            source_element = self._select_source_element(
                source_submodel=source_submodel,
                indexed=source_indexes[source_template_key],
                selector=binding.get("source_selector"),
            )
            if source_element is None:
                failure = self._resolution_payload(
                    status="unresolved",
                    reason="source_selector_no_match",
                    binding=binding,
                    path=path,
                    target_semantic_id=target_semantic_id,
                )
                if first_failure is None:
                    first_failure = failure
                continue

            projection = str(binding.get("projection") or "children").strip().lower()
            if projection != "children":
                failure = self._resolution_payload(
                    status="unresolved",
                    reason=f"unsupported_projection:{projection}",
                    binding=binding,
                    path=path,
                    target_semantic_id=target_semantic_id,
                )
                if first_failure is None:
                    first_failure = failure
                continue

            source_children = self._project_children(source_element)
            if not source_children:
                failure = self._resolution_payload(
                    status="unresolved",
                    reason="source_has_no_children",
                    binding=binding,
                    path=path,
                    target_semantic_id=target_semantic_id,
                )
                if first_failure is None:
                    first_failure = failure
                continue

            applied = self._apply_children_projection(element, source_children)
            if not applied:
                failure = self._resolution_payload(
                    status="unresolved",
                    reason="target_projection_not_supported",
                    binding=binding,
                    path=path,
                    target_semantic_id=target_semantic_id,
                )
                if first_failure is None:
                    first_failure = failure
                continue

            return self._resolution_payload(
                status="resolved",
                reason="ok",
                binding=binding,
                path=path,
                target_semantic_id=target_semantic_id,
            )

        return first_failure

    def _binding_applies(
        self, *, binding: dict[str, Any], template_key: str, model_type: str
    ) -> bool:
        target_templates = binding.get("target_template_keys")
        if isinstance(target_templates, list) and target_templates:
            allowed = {str(entry).strip() for entry in target_templates if str(entry).strip()}
            if template_key not in allowed:
                return False

        target_model_types = binding.get("target_model_types")
        if isinstance(target_model_types, list) and target_model_types:
            allowed_types = {
                str(entry).strip() for entry in target_model_types if str(entry).strip()
            }
            if model_type not in allowed_types:
                return False

        return True

    def _select_source_element(
        self,
        *,
        source_submodel: model.Submodel,
        indexed: list[tuple[str, model.SubmodelElement]],
        selector: Any,
    ) -> model.SubmodelElement | None:
        selector_dict = selector if isinstance(selector, dict) else {}
        selector_path = self._normalize_selector_path(
            str(selector_dict.get("path") or ""),
            source_submodel.id_short,
        )
        selector_semantic = self._normalize_semantic(str(selector_dict.get("semantic_id") or ""))
        selector_model_type = str(selector_dict.get("model_type") or "").strip()

        matches: list[tuple[str, model.SubmodelElement]] = []
        for path, element in indexed:
            rel_path = self._normalize_selector_path(path, source_submodel.id_short)
            if selector_path and rel_path != selector_path:
                continue
            if selector_semantic:
                candidate_semantic = self._normalize_semantic(
                    reference_to_str(getattr(element, "semantic_id", None))
                )
                if candidate_semantic != selector_semantic:
                    continue
            if selector_model_type and type(element).__name__ != selector_model_type:
                continue
            matches.append((rel_path, element))

        if not matches:
            return None

        matches.sort(key=lambda item: (item[0], type(item[1]).__name__))
        return matches[0][1]

    def _project_children(
        self, source_element: model.SubmodelElement
    ) -> list[model.SubmodelElement]:
        if isinstance(source_element, model.SubmodelElementCollection):
            return [
                detach_from_namespace(child) for child in iterable_attr(source_element, "value")
            ]
        if isinstance(source_element, model.SubmodelElementList):
            items = iterable_attr(source_element, "value", "submodel_element", "submodel_elements")
            if not items:
                return []
            first = items[0]
            if isinstance(first, model.SubmodelElementCollection):
                return [detach_from_namespace(child) for child in iterable_attr(first, "value")]
        return []

    def _apply_children_projection(
        self,
        target_element: model.SubmodelElement,
        source_children: list[model.SubmodelElement],
    ) -> bool:
        if not source_children:
            return False

        if isinstance(target_element, model.SubmodelElementCollection):
            cast(Any, target_element).value = source_children
            return True

        if isinstance(target_element, model.SubmodelElementList):
            collection_item = model.SubmodelElementCollection(
                id_short=None,
                value=[detach_from_namespace(child) for child in source_children],
            )
            cast(Any, target_element).type_value_list_element = model.SubmodelElementCollection
            cast(Any, target_element).value = [collection_item]
            return True

        return False

    def _is_structurally_unresolved(self, element: model.SubmodelElement) -> bool:
        if isinstance(element, model.SubmodelElementCollection):
            return (
                len(iterable_attr(element, "value", "submodel_element", "submodel_elements")) == 0
            )

        if isinstance(element, model.SubmodelElementList):
            items = iterable_attr(element, "value", "submodel_element", "submodel_elements")
            if not items:
                return True
            first = items[0]
            if isinstance(first, model.SubmodelElementCollection):
                return (
                    len(iterable_attr(first, "value", "submodel_element", "submodel_elements")) == 0
                )
            return False

        return False

    def _resolution_payload(
        self,
        *,
        status: str,
        reason: str,
        binding: dict[str, Any],
        path: str,
        target_semantic_id: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": status,
            "reason": reason,
            "path": path,
            "target_semantic_id": target_semantic_id,
            "binding_id": str(binding.get("binding_id") or "").strip()
            or self._auto_binding_id(binding),
            "source_template_key": str(binding.get("source_template_key") or "").strip(),
            "source_selector": self._sorted_dict(binding.get("source_selector")),
        }
        target_templates = binding.get("target_template_keys")
        if isinstance(target_templates, list) and target_templates:
            payload["target_template_keys"] = sorted(
                str(entry) for entry in target_templates if str(entry).strip()
            )
        return payload

    def _auto_binding_id(self, binding: dict[str, Any]) -> str:
        source = str(binding.get("source_template_key") or "unknown")
        selector = binding.get("source_selector") or {}
        semantic = str(selector.get("semantic_id") or "")
        model_type = str(selector.get("model_type") or "")
        path = str(selector.get("path") or "")
        descriptor = ":".join(part for part in (source, semantic, model_type, path) if part)
        return descriptor or "dropin-binding"

    def _walk_elements(
        self,
        submodel: model.Submodel,
    ) -> list[tuple[str, model.SubmodelElement]]:
        root = submodel.id_short or "Submodel"
        walk: list[tuple[str, model.SubmodelElement]] = []

        def recurse(path: str, element: model.SubmodelElement) -> None:
            walk.append((path, element))

            if isinstance(element, model.SubmodelElementCollection):
                for child in iterable_attr(
                    element, "value", "submodel_element", "submodel_elements"
                ):
                    child_id = getattr(child, "id_short", None) or type(child).__name__
                    recurse(f"{path}/{child_id}", child)
                return

            if isinstance(element, model.SubmodelElementList):
                for child in iterable_attr(
                    element, "value", "submodel_element", "submodel_elements"
                ):
                    recurse(f"{path}[]", child)
                return

            if isinstance(element, model.Entity):
                for statement in iterable_attr(element, "statement", "statements"):
                    statement_id = getattr(statement, "id_short", None) or type(statement).__name__
                    recurse(f"{path}/statements/{statement_id}", statement)
                return

            if isinstance(element, model.AnnotatedRelationshipElement):
                for annotation in iterable_attr(element, "annotation", "annotations"):
                    annotation_id = (
                        getattr(annotation, "id_short", None) or type(annotation).__name__
                    )
                    recurse(f"{path}/annotations/{annotation_id}", annotation)
                return

            if isinstance(element, model.Operation):
                for var_kind in ("input_variable", "output_variable", "in_output_variable"):
                    for variable in iterable_attr(element, var_kind):
                        var_id = getattr(variable, "id_short", None) or type(variable).__name__
                        recurse(f"{path}/{var_kind}/{var_id}", variable)

        for element in iterable_attr(submodel, "submodel_element", "submodel_elements"):
            node_id = element.id_short or type(element).__name__
            recurse(f"{root}/{node_id}", element)

        walk.sort(key=lambda item: item[0])
        return walk

    def _normalize_semantic(self, value: str | None) -> str:
        if not value:
            return ""
        return value.strip().rstrip("/").lower()

    def _normalize_selector_path(self, value: str, root_id_short: str | None) -> str:
        normalized = value.strip().strip("/")
        if not normalized:
            return ""
        if root_id_short:
            prefix = f"{root_id_short}/"
            if normalized.startswith(prefix):
                return normalized[len(prefix) :]
            if normalized == root_id_short:
                return ""
        return normalized

    def _sorted_dict(self, value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        payload: dict[str, Any] = {}
        for key in sorted(value.keys()):
            item = value[key]
            if isinstance(item, list):
                payload[str(key)] = list(item)
            else:
                payload[str(key)] = item
        return payload
