"""
Export Service for DPP data in various formats.
Supports AASX, JSON, and PDF export with integrity verification.
"""

import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID
from xml.etree import ElementTree as ET

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
                "exportedAt": datetime.now(timezone.utc).isoformat(),
                "revisionNo": revision.revision_no,
                "digestSha256": revision.digest_sha256,
                "signedJws": revision.signed_jws,
            },
        }

        # Canonical JSON with sorted keys
        return json.dumps(
            export_data,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        ).encode("utf-8")

    def export_aasx(self, revision: DPPRevision, dpp_id: UUID) -> bytes:
        """
        Export DPP as AASX package.

        Creates an AASX file following IDTA Part 5 specification.
        AASX is a ZIP archive with specific structure and relationships.
        """
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Create [Content_Types].xml
            content_types = self._create_content_types()
            zf.writestr("[Content_Types].xml", content_types)

            # 2. Create _rels/.rels (root relationships)
            root_rels = self._create_root_rels()
            zf.writestr("_rels/.rels", root_rels)

            # 3. Create aasx/aas.json (main AAS content)
            aas_json = json.dumps(
                revision.aas_env_json,
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
            )
            zf.writestr("aasx/aas.json", aas_json)

            # 4. Create aasx/_rels/aas.json.rels (AAS relationships)
            aas_rels = self._create_aas_rels()
            zf.writestr("aasx/_rels/aas.json.rels", aas_rels)

            # 5. Create aasx-origin file
            origin_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<origin xmlns="http://www.admin-shell.io/aasx/origin">
    <created>{datetime.now(timezone.utc).isoformat()}</created>
    <creator>Mini DPP Platform v{self._settings.version}</creator>
    <dppId>{dpp_id}</dppId>
    <revisionNo>{revision.revision_no}</revisionNo>
    <digest algorithm="SHA-256">{revision.digest_sha256}</digest>
</origin>"""
            zf.writestr("aasx/aasx-origin", origin_content)

            # 6. Create metadata/core-properties.xml (Dublin Core)
            core_props = self._create_core_properties(revision, dpp_id)
            zf.writestr("metadata/core-properties.xml", core_props)

        buffer.seek(0)
        return buffer.read()

    def _create_content_types(self) -> str:
        """Create AASX content types XML."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="json" ContentType="application/json"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Override PartName="/metadata/core-properties.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"""

    def _create_root_rels(self) -> str:
        """Create root relationships file."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://www.admin-shell.io/aasx/relationships/aas-spec" Target="/aasx/aas.json"/>
    <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="/metadata/core-properties.xml"/>
</Relationships>"""

    def _create_aas_rels(self) -> str:
        """Create AAS relationships file."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://www.admin-shell.io/aasx/relationships/aasx-origin" Target="aasx-origin"/>
</Relationships>"""

    def _create_core_properties(
        self,
        revision: DPPRevision,
        dpp_id: UUID,
    ) -> str:
        """Create Dublin Core metadata file."""
        now = datetime.now(timezone.utc).isoformat()

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<coreProperties xmlns="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                xmlns:dc="http://purl.org/dc/elements/1.1/"
                xmlns:dcterms="http://purl.org/dc/terms/">
    <dc:title>Digital Product Passport</dc:title>
    <dc:identifier>{dpp_id}</dc:identifier>
    <dc:creator>Mini DPP Platform</dc:creator>
    <dcterms:created>{revision.created_at.isoformat()}</dcterms:created>
    <dcterms:modified>{now}</dcterms:modified>
    <dc:description>AASX package containing DPP revision {revision.revision_no}</dc:description>
</coreProperties>"""

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
                        ET.fromstring(content_types)
                    except ET.ParseError as e:
                        errors.append(f"Invalid Content_Types.xml: {e}")

                # Validate relationships
                if "_rels/.rels" in names:
                    try:
                        rels = zf.read("_rels/.rels")
                        ET.fromstring(rels)
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
