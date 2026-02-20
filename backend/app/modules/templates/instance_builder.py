"""Build sandbox AAS instances from template contracts + form data."""

from __future__ import annotations

import io
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

import pyecma376_2
from basyx.aas import model
from basyx.aas.adapter import aasx
from basyx.aas.adapter import json as basyx_json

from app.core.logging import get_logger
from app.db.models import Template
from app.modules.dpps.basyx_builder import BasyxDppBuilder
from app.modules.templates.service import TemplateRegistryService

logger = get_logger(__name__)


class TemplateInstanceBuilder:
    """Instantiate a deterministic single-submodel AAS environment for sandbox use."""

    def __init__(self, template_service: TemplateRegistryService) -> None:
        self._template_service = template_service
        self._delegate = BasyxDppBuilder(template_service)

    def build_environment(
        self,
        *,
        template: Template,
        data: dict[str, Any],
        template_lookup: Mapping[str, Template] | None = None,
    ) -> dict[str, Any]:
        """Build AAS environment with one shell and one instantiated submodel."""
        asset_ids = {
            "manufacturerPartId": "sandbox",
            "globalAssetId": f"urn:dpp:sandbox:{template.template_key}",
        }
        resolved_lookup = dict(template_lookup or {template.template_key: template})
        resolved_lookup.setdefault(template.template_key, template)

        parsed = self._delegate._parse_template(
            template,
            template.semantic_id,
            template_key=template.template_key,
            template_lookup=resolved_lookup,
        )
        submodel = self._delegate._instantiate_submodel(
            template.template_key,
            asset_ids,
            parsed.submodel,
            data,
        )

        store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
        aas_shell = self._delegate._build_aas(asset_ids)
        store.add(aas_shell)
        store.add(submodel)
        aas_shell.submodel.add(model.ModelReference.from_referable(submodel))

        for concept_description in parsed.concept_descriptions:
            try:
                store.add(concept_description)
            except Exception:
                # Duplicate concept descriptions are safe to skip in sandbox exports.
                continue

        payload = basyx_json.object_store_to_json(store)  # type: ignore[attr-defined]
        if isinstance(payload, str):
            return cast(dict[str, Any], json.loads(payload))
        return cast(dict[str, Any], payload)

    def to_json_bytes(self, aas_environment: dict[str, Any]) -> bytes:
        return json.dumps(
            aas_environment,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        ).encode("utf-8")

    def to_aasx_bytes(self, aas_environment: dict[str, Any]) -> bytes:
        buffer = io.BytesIO()
        payload = json.dumps(aas_environment, sort_keys=True, indent=2, ensure_ascii=False)
        string_io = io.StringIO(payload)
        try:
            store = basyx_json.read_aas_json_file(string_io, failsafe=True)  # type: ignore[attr-defined]
        finally:
            string_io.close()

        files = aasx.DictSupplementaryFileContainer()  # type: ignore[no-untyped-call]
        with aasx.AASXWriter(buffer) as writer:
            core_props = pyecma376_2.OPCCoreProperties()  # type: ignore[attr-defined, no-untyped-call]
            core_props.created = datetime.now(UTC)
            core_props.modified = datetime.now(UTC)
            core_props.creator = "Mini DPP Platform"
            core_props.title = "Sandbox AAS Export"
            core_props.subject = "IDTA Submodel Template Sandbox"
            writer.write_core_properties(core_props)
            writer.write_all_aas_objects("/aasx/data.json", store, files, write_json=True)
        buffer.seek(0)
        return buffer.read()

    def to_pdf_bytes(
        self,
        aas_environment: dict[str, Any],
        *,
        template_key: str,
        version: str,
    ) -> bytes:
        try:
            from fpdf import FPDF  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover - dependency error
            logger.error("pdf_export_dependency_missing", error=str(exc))
            raise RuntimeError("PDF export dependency missing") from exc

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "AAS Developer Sandbox Export", ln=True)

        pdf.set_font("Helvetica", size=11)
        pdf.cell(0, 8, f"Template: {template_key}", ln=True)
        pdf.cell(0, 8, f"Version: {version}", ln=True)
        pdf.cell(0, 8, f"Generated: {datetime.now(UTC).isoformat()}", ln=True)

        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "AAS Environment (JSON)", ln=True)

        pdf.set_font("Courier", size=8)
        aas_json = json.dumps(aas_environment, indent=2, ensure_ascii=True)
        pdf.multi_cell(0, 4, aas_json)

        output = cast(str | bytes | bytearray, pdf.output(dest="S"))
        if isinstance(output, (bytes, bytearray)):
            return bytes(output)
        return output.encode("latin-1")
