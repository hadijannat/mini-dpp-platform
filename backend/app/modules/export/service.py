"""
Export Service for DPP data in various formats.
Supports AASX, JSON, and PDF export with integrity verification.
"""

import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import UUID
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DefusedET
import pyecma376_2
from basyx.aas.adapter import aasx
from basyx.aas.adapter import json as basyx_json

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import DPPRevision

logger = get_logger(__name__)

ExportFormat = Literal["json", "aasx", "pdf"]


class ExportService:
    """
    Service for exporting DPP data in standardized formats.

    Implements IDTA Part 5 AASX package format and provides
    integrity verification through embedded digests.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    def export_json(self, revision: DPPRevision) -> bytes:
        """
        Export DPP as canonical JSON.

        Returns the AAS Environment JSON with metadata
        including digest and timestamp.
        """
        export_data = {
            "aasEnvironment": revision.aas_env_json,
            "metadata": {
                "exportedAt": datetime.now(UTC).isoformat(),
                "revisionNo": revision.revision_no,
                "digestSha256": revision.digest_sha256,
                "signedJws": revision.signed_jws,
                "signingKeyId": self._settings.dpp_signing_key_id if revision.signed_jws else None,
                "signingAlgorithm": (
                    self._settings.dpp_signing_algorithm if revision.signed_jws else None
                ),
            },
        }

        # Canonical JSON with sorted keys
        return json.dumps(
            export_data,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        ).encode("utf-8")

    def export_aasx(
        self,
        revision: DPPRevision,
        dpp_id: UUID,
        write_json: bool = True,
    ) -> bytes:
        """
        Export DPP as AASX package.

        Creates an AASX file following IDTA Part 5 specification.
        AASX is a ZIP archive with specific structure and relationships.

        Args:
            revision: The DPP revision to export
            dpp_id: DPP identifier for metadata
            write_json: If True (default) serialize as JSON, if False as XML
        """
        buffer = io.BytesIO()
        try:
            payload = json.dumps(
                revision.aas_env_json,
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
            )
            string_io = io.StringIO(payload)
            try:
                store = basyx_json.read_aas_json_file(  # type: ignore[attr-defined]
                    string_io
                )
            finally:
                string_io.close()

            files = aasx.DictSupplementaryFileContainer()  # type: ignore[no-untyped-call]

            with aasx.AASXWriter(buffer) as writer:
                core_props = pyecma376_2.OPCCoreProperties()  # type: ignore[attr-defined, no-untyped-call]
                core_props.created = revision.created_at
                core_props.modified = datetime.now(UTC)
                core_props.creator = "Mini DPP Platform"
                core_props.title = f"DPP {dpp_id}"
                core_props.description = (
                    f"AASX package containing DPP revision {revision.revision_no}"
                )
                core_props.subject = "Digital Product Passport (IDTA DPP4.0)"
                core_props.category = "AAS Package"
                core_props.identifier = str(dpp_id)
                core_props.version = self._settings.version
                core_props.revision = str(revision.revision_no)
                writer.write_core_properties(core_props)
                data_path = "/aasx/data.json" if write_json else "/aasx/data.xml"
                writer.write_all_aas_objects(data_path, store, files, write_json=write_json)

            buffer.seek(0)
            return buffer.read()
        except Exception as exc:
            logger.error("aasx_export_failed", dpp_id=str(dpp_id), error=str(exc))
            raise ValueError(f"Failed to export AASX: {exc}") from exc
        finally:
            buffer.close()

    def export_pdf(self, revision: DPPRevision, dpp_id: UUID) -> bytes:
        """
        Export DPP as a simple PDF summary.

        The PDF includes basic metadata and a JSON snapshot of the AAS environment.
        """
        try:
            from fpdf import FPDF  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover - dependency error
            logger.error("pdf_export_dependency_missing", error=str(exc))
            raise RuntimeError("PDF export dependency missing") from exc

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Digital Product Passport", ln=True)

        pdf.set_font("Helvetica", size=11)
        pdf.cell(0, 8, f"DPP ID: {dpp_id}", ln=True)
        pdf.cell(0, 8, f"Revision: {revision.revision_no}", ln=True)
        pdf.cell(0, 8, f"Digest (SHA-256): {revision.digest_sha256}", ln=True)
        if revision.signed_jws:
            pdf.multi_cell(0, 6, f"Signature (JWS): {revision.signed_jws}")

        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "AAS Environment (JSON)", ln=True)

        pdf.set_font("Courier", size=8)
        aas_json = json.dumps(revision.aas_env_json, indent=2, ensure_ascii=True)
        pdf.multi_cell(0, 4, aas_json)

        output = cast(str | bytes | bytearray, pdf.output(dest="S"))
        if isinstance(output, (bytes, bytearray)):
            return bytes(output)
        return output.encode("latin-1")

    def validate_aasx(self, aasx_bytes: bytes) -> dict[str, Any]:
        """
        Validate an AASX package structure.

        Checks for required files and relationships per IDTA Part 5.
        """
        errors: list[str] = []
        warnings: list[str] = []

        try:
            with zipfile.ZipFile(io.BytesIO(aasx_bytes), "r") as zf:
                names = zf.namelist()

                # Check required files
                required_files = [
                    "[Content_Types].xml",
                    "_rels/.rels",
                ]

                for req in required_files:
                    if req not in names:
                        errors.append(f"Missing required file: {req}")

                # Check for AAS content
                aas_files = [n for n in names if n.endswith(".json") and "aas" in n.lower()]
                if not aas_files:
                    errors.append("No AAS JSON file found")

                # Validate Content_Types.xml
                if "[Content_Types].xml" in names:
                    try:
                        content_types = zf.read("[Content_Types].xml")
                        DefusedET.fromstring(content_types)
                    except ET.ParseError as e:
                        errors.append(f"Invalid Content_Types.xml: {e}")

                # Validate relationships
                if "_rels/.rels" in names:
                    try:
                        rels = zf.read("_rels/.rels")
                        DefusedET.fromstring(rels)
                    except ET.ParseError as e:
                        errors.append(f"Invalid _rels/.rels: {e}")

        except zipfile.BadZipFile:
            errors.append("Invalid ZIP archive")
        except Exception as e:
            errors.append(f"Validation error: {e}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }
