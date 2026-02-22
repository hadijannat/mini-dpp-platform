"""
Export Service for DPP data in various formats.
Supports AASX, JSON, and PDF export with integrity verification.
"""

import io
import json
import posixpath
import zipfile
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import UUID
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DefusedET
import pyecma376_2
from basyx.aas import model
from basyx.aas.adapter import aasx
from basyx.aas.adapter import json as basyx_json
from basyx.aas.adapter import xml as basyx_xml

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import DPPRevision
from app.modules.epcis.schemas import EPCISEventResponse

logger = get_logger(__name__)

ExportFormat = Literal["json", "aasx", "xml", "pdf"]


class ExportService:
    """
    Service for exporting DPP data in standardized formats.

    Implements IDTA Part 5 AASX package format and provides
    integrity verification through embedded digests.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    @staticmethod
    def _resolve_export_environment(
        revision: DPPRevision,
        aas_env_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if isinstance(aas_env_json, dict):
            return aas_env_json
        return revision.aas_env_json

    @staticmethod
    def inject_traceability_submodel(
        revision: DPPRevision,
        epcis_events: list[EPCISEventResponse],
        *,
        epcis_endpoint_url: str | None = None,
        digital_link_uri: str | None = None,
    ) -> None:
        """Inject EPCIS Traceability submodel into the revision's AAS environment.

        Mutates ``revision.aas_env_json`` in-place (the revision object is not
        persisted after export, so this is safe). No-op if events list is empty.
        """
        from app.modules.epcis.aas_bridge import build_traceability_submodel

        submodel = build_traceability_submodel(
            epcis_events,
            epcis_endpoint_url=epcis_endpoint_url,
            digital_link_uri=digital_link_uri,
        )
        if submodel is None:
            return

        aas_env = revision.aas_env_json
        if not isinstance(aas_env, dict):
            return

        submodels = aas_env.setdefault("submodels", [])
        submodels.append(submodel)

    def export_json(
        self,
        revision: DPPRevision,
        aas_env_json: dict[str, Any] | None = None,
    ) -> bytes:
        """
        Export DPP as canonical JSON.

        Returns the AAS Environment JSON with metadata
        including digest and timestamp.
        """
        export_data = {
            "aasEnvironment": self._resolve_export_environment(revision, aas_env_json),
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

    def export_jsonld(
        self,
        revision: DPPRevision,
        aas_env_json: dict[str, Any] | None = None,
    ) -> bytes:
        """Export DPP as JSON-LD (Linked Data).

        Returns the AAS environment converted to JSON-LD with proper
        ``@context`` and ``@graph`` structure.
        """
        from app.modules.aas import aas_to_jsonld

        jsonld = aas_to_jsonld(self._resolve_export_environment(revision, aas_env_json))
        return json.dumps(jsonld, indent=2, ensure_ascii=False).encode("utf-8")

    def export_turtle(
        self,
        revision: DPPRevision,
        aas_env_json: dict[str, Any] | None = None,
    ) -> bytes:
        """Export DPP as Turtle (RDF).

        Returns the AAS environment serialized as Turtle via rdflib.
        """
        from app.modules.aas import aas_to_turtle

        turtle_str = aas_to_turtle(self._resolve_export_environment(revision, aas_env_json))
        return turtle_str.encode("utf-8")

    def export_xml(
        self,
        revision: DPPRevision,
        aas_env_json: dict[str, Any] | None = None,
    ) -> bytes:
        """Export DPP as AAS XML.

        Serializes the AAS environment to XML format using BaSyx's
        built-in XML serializer with proper AAS Part 1 namespaces.
        """
        export_env = self._resolve_export_environment(revision, aas_env_json)
        payload = json.dumps(
            export_env,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        )
        string_io = io.StringIO(payload)
        try:
            # Use failsafe=True for export: we're round-tripping already-validated
            # stored data.  Strict validation belongs at ingestion (parser/builder).
            store = basyx_json.read_aas_json_file(  # type: ignore[attr-defined]
                string_io, failsafe=True
            )
        except Exception as exc:
            logger.error("export_xml_deserialization_failed", exc_info=True)
            raise ValueError(
                "Failed to export XML: AAS environment contains malformed elements"
            ) from exc
        finally:
            string_io.close()

        xml_buffer = io.BytesIO()
        basyx_xml.write_aas_xml_file(xml_buffer, store)  # type: ignore[attr-defined]
        xml_buffer.seek(0)
        return xml_buffer.read()

    def export_aasx(
        self,
        revision: DPPRevision,
        dpp_id: UUID,
        write_json: bool = True,
        supplementary_files: list[dict[str, Any]] | None = None,
        aas_env_json: dict[str, Any] | None = None,
        data_json_override: dict[str, Any] | None = None,
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
            export_env = self._resolve_export_environment(revision, aas_env_json)
            payload = json.dumps(
                export_env,
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
            )
            string_io = io.StringIO(payload)
            try:
                # Use failsafe=True for export: we're round-tripping already-validated
                # stored data.  Strict validation belongs at ingestion (parser/builder).
                store = basyx_json.read_aas_json_file(  # type: ignore[attr-defined]
                    string_io, failsafe=True
                )
            except Exception as exc:
                if not write_json or data_json_override is None:
                    logger.error("export_aasx_deserialization_failed", exc_info=True)
                    raise ValueError(
                        "Failed to export AASX: AAS environment contains malformed elements"
                    ) from exc
                fallback_payload = json.dumps(
                    revision.aas_env_json,
                    sort_keys=True,
                    indent=2,
                    ensure_ascii=False,
                )
                fallback_io = io.StringIO(fallback_payload)
                try:
                    store = basyx_json.read_aas_json_file(  # type: ignore[attr-defined]
                        fallback_io, failsafe=True
                    )
                except Exception as fallback_exc:
                    logger.error("export_aasx_deserialization_failed", exc_info=True)
                    raise ValueError(
                        "Failed to export AASX: AAS environment contains malformed elements"
                    ) from fallback_exc
                finally:
                    fallback_io.close()
            finally:
                string_io.close()

            files = aasx.DictSupplementaryFileContainer()  # type: ignore[no-untyped-call]
            for supplementary in supplementary_files or []:
                package_path = self._normalize_package_path(supplementary.get("package_path"))
                file_payload = supplementary.get("payload")
                content_type = str(supplementary.get("content_type") or "application/octet-stream")
                if not package_path or not isinstance(file_payload, (bytes, bytearray)):
                    continue
                files.add_file(package_path, io.BytesIO(bytes(file_payload)), content_type)

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
            result = buffer.read()
            if write_json and isinstance(data_json_override, dict):
                result = self._replace_aasx_data_json(result, data_json_override)
            return result
        except ValueError:
            raise  # Already sanitized by inner handler
        except Exception as exc:
            logger.error("aasx_export_failed", dpp_id=str(dpp_id), exc_info=True)
            raise ValueError("Failed to export AASX: package creation failed") from exc
        finally:
            buffer.close()

    def _replace_aasx_data_json(self, aasx_bytes: bytes, data_json: dict[str, Any]) -> bytes:
        replacement = json.dumps(
            data_json,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        ).encode("utf-8")

        source = io.BytesIO(aasx_bytes)
        target = io.BytesIO()
        replaced = False
        with (
            zipfile.ZipFile(source, "r") as archive,
            zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as output,
        ):
            for entry in archive.infolist():
                normalized = entry.filename.replace("\\", "/").lstrip("/")
                if normalized.lower() == "aasx/data.json":
                    output.writestr("aasx/data.json", replacement)
                    replaced = True
                    continue
                output.writestr(entry.filename, archive.read(entry.filename))
            if not replaced:
                output.writestr("aasx/data.json", replacement)
        target.seek(0)
        return target.read()

    def _normalize_package_path(self, raw_path: Any) -> str | None:
        if not isinstance(raw_path, str):
            return None
        path = raw_path.replace("\\", "/").strip()
        if not path:
            return None
        if not path.startswith("/"):
            path = f"/{path}"
        normalized = posixpath.normpath(path)
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        if normalized in {"/", "/."}:
            return None
        if not normalized.startswith("/aasx/files/"):
            return None
        return normalized

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

    def validate_aasx_structure(self, aasx_bytes: bytes) -> dict[str, Any]:
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

                # Check for AAS content (JSON or XML)
                aas_json = [n for n in names if n.endswith(".json") and "aas" in n.lower()]
                aas_xml_files = [n for n in names if n.endswith(".xml") and "data" in n.lower()]
                aas_files = aas_json or aas_xml_files
                if not aas_files:
                    errors.append("No AAS data file found (JSON or XML)")

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

    def validate_aasx(self, aasx_bytes: bytes) -> dict[str, Any]:
        """Validate AASX — full compliance check including BaSyx round-trip."""
        return self.validate_aasx_compliance(aasx_bytes)

    def validate_aasx_compliance(self, aasx_bytes: bytes) -> dict[str, Any]:
        """
        Validate AASX compliance via BaSyx round-trip deserialization.

        Attempts to read the AASX package back through BaSyx's AASXReader
        and then re-serialize. Any deserialization errors indicate the package
        is not fully compliant with the AAS metamodel.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # First run structural validation
        structural = self.validate_aasx_structure(aasx_bytes)
        errors.extend(structural["errors"])
        warnings.extend(structural["warnings"])

        if errors:
            return {"valid": False, "errors": errors, "warnings": warnings}

        # Round-trip: read AASX → object store → serialize back to JSON
        try:
            store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
            files = aasx.DictSupplementaryFileContainer()  # type: ignore[no-untyped-call]
            with aasx.AASXReader(io.BytesIO(aasx_bytes)) as reader:
                reader.read_into(store, files)

            identifiables = list(store)
            if not identifiables:
                # BaSyx's lenient mode may skip objects it can't fully parse;
                # this is a warning rather than a hard error since the AASX
                # structure itself is valid.
                warnings.append(
                    "BaSyx could not deserialize any identifiable objects from the AASX "
                    "(lenient mode may have skipped non-compliant entries)"
                )
            else:
                # Verify we can serialize back to JSON without errors
                basyx_json.object_store_to_json(store)  # type: ignore[attr-defined]

        except Exception as exc:
            errors.append(f"BaSyx compliance check failed: {exc}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }
