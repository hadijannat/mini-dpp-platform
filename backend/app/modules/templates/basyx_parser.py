"""BaSyx-based template parser utilities."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from basyx.aas import model
from basyx.aas.adapter import aasx
from basyx.aas.adapter import json as basyx_json

from app.core.logging import get_logger
from app.modules.aas.references import reference_to_str

logger = get_logger(__name__)


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
        with aasx.AASXReader(io.BytesIO(aasx_bytes)) as reader:
            file_store = aasx.DictSupplementaryFileContainer()  # type: ignore[no-untyped-call]
            reader.read_into(store, file_store)
        return self._build_parsed(store, expected_semantic_id)

    def parse_json(
        self,
        json_bytes: bytes,
        expected_semantic_id: str | None = None,
        *,
        strict: bool = False,
    ) -> ParsedTemplate:
        """Parse a JSON AAS environment into a :class:`ParsedTemplate`.

        Args:
            json_bytes: Raw UTF-8 encoded JSON.
            expected_semantic_id: If given, select the submodel matching this semantic ID.
            strict: When ``True``, pass ``failsafe=False`` to BaSyx's JSON
                    deserializer so that malformed elements raise immediately
                    instead of being silently skipped.
        """
        try:
            payload = json_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"JSON bytes are not valid UTF-8: {exc}") from exc

        string_io = io.StringIO(payload)
        try:
            if strict:
                store = basyx_json.read_aas_json_file(  # type: ignore[attr-defined]
                    string_io, failsafe=False
                )
            else:
                store = basyx_json.read_aas_json_file(string_io)  # type: ignore[attr-defined]
        finally:
            string_io.close()
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
                if expected_semantic_id in (reference_to_str(sm.semantic_id) or "")
            ]
            if len(matching) == 1:
                return matching[0]
            if not matching:
                logger.warning(
                    "template_semantic_id_mismatch",
                    expected=expected_semantic_id,
                    available=[reference_to_str(sm.semantic_id) for sm in submodels],
                )
            # No match or multiple matches - fall through to other selection

        template_kind = [
            sm for sm in submodels if getattr(sm, "kind", None) == model.ModellingKind.TEMPLATE
        ]
        if len(template_kind) == 1:
            return template_kind[0]

        if len(submodels) == 1:
            return submodels[0]

        if template_kind:
            logger.warning(
                "template_ambiguous_submodel_selection",
                count=len(template_kind),
                selected=template_kind[0].id_short,
            )
            return template_kind[0]

        raise ValueError(f"Ambiguous template payload: {len(submodels)} submodels found")
