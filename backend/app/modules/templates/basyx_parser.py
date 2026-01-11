"""BaSyx-based template parser utilities."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from typing import Any

from basyx.aas import model
from basyx.aas.adapter import aasx
from basyx.aas.adapter import json as basyx_json


@dataclass(frozen=True)
class ParsedTemplate:
    store: model.DictObjectStore[model.Identifiable]
    submodel: model.Submodel
    concept_descriptions: list[Any]


class BasyxTemplateParser:
    """Parse AASX/JSON templates into BaSyx object stores."""

    def parse_aasx(
        self, aasx_bytes: bytes, expected_semantic_id: str | None = None
    ) -> ParsedTemplate:
        store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
        with tempfile.NamedTemporaryFile(suffix=".aasx") as fp:
            fp.write(aasx_bytes)
            fp.flush()
            with aasx.AASXReader(fp) as reader:
                file_store = aasx.DictSupplementaryFileContainer()  # type: ignore[no-untyped-call]
                reader.read_into(store, file_store)
        return self._build_parsed(store, expected_semantic_id)

    def parse_json(
        self, json_bytes: bytes, expected_semantic_id: str | None = None
    ) -> ParsedTemplate:
        with tempfile.NamedTemporaryFile(suffix=".json") as fp:
            fp.write(json_bytes)
            fp.flush()
            store = basyx_json.read_aas_json_file(fp.name)  # type: ignore[attr-defined]
        return self._build_parsed(store, expected_semantic_id)

    def _build_parsed(
        self,
        store: model.DictObjectStore[model.Identifiable],
        expected_semantic_id: str | None,
    ) -> ParsedTemplate:
        submodel = self._select_submodel(store, expected_semantic_id)
        concept_desc_type = getattr(model, "ConceptDescription", None)
        if concept_desc_type is None:
            concept_descriptions = []
        else:
            concept_descriptions = [obj for obj in store if isinstance(obj, concept_desc_type)]
            concept_descriptions.sort(
                key=lambda cd: (
                    str(getattr(cd, "id", "")),
                    str(getattr(cd, "id_short", "")),
                )
            )
        return ParsedTemplate(
            store=store,
            submodel=submodel,
            concept_descriptions=concept_descriptions,
        )

    def _select_submodel(
        self,
        store: model.DictObjectStore[model.Identifiable],
        expected_semantic_id: str | None,
    ) -> model.Submodel:
        submodels = [obj for obj in store if isinstance(obj, model.Submodel)]
        if not submodels:
            raise ValueError("No Submodel found in template payload")

        if expected_semantic_id:
            matching = [
                sm
                for sm in submodels
                if expected_semantic_id in (self._reference_to_str(sm.semantic_id) or "")
            ]
            if len(matching) == 1:
                return matching[0]

        template_kind = [
            sm for sm in submodels if getattr(sm, "kind", None) == model.ModellingKind.TEMPLATE
        ]
        if len(template_kind) == 1:
            return template_kind[0]

        if len(submodels) == 1:
            return submodels[0]

        if template_kind:
            return template_kind[0]

        raise ValueError(f"Ambiguous template payload: {len(submodels)} submodels found")

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
