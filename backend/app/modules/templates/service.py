"""
Template Registry Service for IDTA Submodel Templates.
Handles fetching, parsing, caching, and versioning of DPP4.0 templates.
"""

import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import Template
from app.modules.templates.basyx_parser import BasyxTemplateParser
from app.modules.templates.catalog import (
    TemplateDescriptor,
    get_template_descriptor,
    list_template_keys,
)
from app.modules.templates.definition import TemplateDefinitionBuilder
from app.modules.templates.qualifiers import parse_allowed_range, parse_smt_qualifiers

logger = get_logger(__name__)


class TemplateFetchError(RuntimeError):
    """Raised when a template cannot be fetched or parsed from upstream sources."""

    def __init__(self, template_key: str, version: str, message: str) -> None:
        super().__init__(message)
        self.template_key = template_key
        self.version = version


class TemplateParseError(RuntimeError):
    """Raised when a template cannot be parsed into the BaSyx object model."""

    def __init__(self, template_key: str, version: str, message: str) -> None:
        super().__init__(message)
        self.template_key = template_key
        self.version = version


class TemplateRegistryService:
    """
    Manages IDTA submodel templates for DPP creation and editing.

    Provides template fetching, caching, normalization, and version management.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for template fetching."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def get_all_templates(self) -> list[Template]:
        """
        Get all registered templates from the database.

        Returns templates ordered by template_key for consistent display.
        """
        result = await self._session.execute(select(Template).order_by(Template.template_key))
        return list(result.scalars().all())

    async def get_template(
        self,
        template_key: str,
        version: str | None = None,
    ) -> Template | None:
        """
        Get a specific template by key and optional version.

        If version is not specified, returns the pinned version from config.
        """
        if version is None:
            version = self._settings.template_versions.get(template_key)
            if version is None:
                logger.warning("unknown_template_key", template_key=template_key)
                return None

        result = await self._session.execute(
            select(Template).where(
                Template.template_key == template_key,
                Template.idta_version == version,
            )
        )
        return result.scalar_one_or_none()

    async def refresh_template(self, template_key: str) -> Template:
        """
        Fetch or update a template from IDTA repository.

        Downloads the AASX package, extracts and normalizes the AAS environment,
        and stores both the original package and normalized JSON.
        """
        descriptor = get_template_descriptor(template_key)
        if descriptor is None:
            raise ValueError(f"Unknown template key: {template_key}")

        version = self._settings.template_versions.get(template_key)
        if version is None:
            raise ValueError(f"No pinned version configured for template: {template_key}")

        # Resolve source URLs based on IDTA repo structure
        json_url, aasx_url = await self._resolve_template_assets(descriptor, version)
        if not json_url and not aasx_url:
            json_url = self._build_template_url(descriptor, version, file_kind="json")
            aasx_url = self._build_template_url(descriptor, version, file_kind="aasx")

        logger.info(
            "fetching_template",
            template_key=template_key,
            version=version,
            json_url=json_url,
            aasx_url=aasx_url,
        )

        aas_env_json: dict[str, Any] | None = None
        template_aasx: bytes | None = None
        source_url: str | None = None

        client = await self._get_http_client()

        if json_url:
            try:
                response = await client.get(json_url)
                response.raise_for_status()
                payload = response.json()
                aas_env_json = self._normalize_template_json(payload, template_key)
                source_url = json_url
                if not aas_env_json.get("submodels"):
                    logger.warning(
                        "template_empty_submodels",
                        template_key=template_key,
                        version=version,
                        source_url=json_url,
                    )
                    aas_env_json = None
            except Exception as e:
                logger.warning(
                    "template_json_fetch_failed",
                    template_key=template_key,
                    version=version,
                    source_url=json_url,
                    error=str(e),
                )

        if aas_env_json is None and aasx_url:
            try:
                response = await client.get(aasx_url)
                response.raise_for_status()
                template_aasx = response.content
                aas_env_json = self._extract_aas_environment(template_aasx)
                source_url = aasx_url
                if not aas_env_json.get("submodels"):
                    logger.warning(
                        "template_empty_submodels",
                        template_key=template_key,
                        version=version,
                        source_url=aasx_url,
                    )
                    aas_env_json = None
            except Exception as e:
                logger.warning(
                    "template_aasx_fetch_failed",
                    template_key=template_key,
                    version=version,
                    source_url=aasx_url,
                    error=str(e),
                )

        if aas_env_json is None:
            logger.error(
                "template_fetch_failed",
                template_key=template_key,
                version=version,
                json_url=json_url,
                aasx_url=aasx_url,
            )
            raise TemplateFetchError(
                template_key,
                version,
                "Template fetch/parse failed; no valid AAS environment found.",
            )

        semantic_id = descriptor.semantic_id

        # Upsert template record
        existing = await self.get_template(template_key, version)

        if existing:
            existing.template_json = aas_env_json
            if template_aasx is not None:
                existing.template_aasx = template_aasx
            if source_url is not None:
                existing.source_url = source_url
            existing.fetched_at = datetime.now(UTC)
            template = existing
        else:
            template = Template(
                template_key=template_key,
                idta_version=version,
                semantic_id=semantic_id,
                source_url=source_url or (json_url or aasx_url or ""),
                template_aasx=template_aasx,
                template_json=aas_env_json,
                fetched_at=datetime.now(UTC),
            )
            self._session.add(template)

        await self._session.flush()

        logger.info(
            "template_refreshed",
            template_key=template_key,
            version=version,
            submodel_count=len(aas_env_json.get("submodels", [])),
        )

        return template

    def generate_template_definition(self, template: Template) -> dict[str, Any]:
        descriptor = get_template_descriptor(template.template_key)
        if descriptor is None:
            raise ValueError(f"Unknown template key: {template.template_key}")

        parser = BasyxTemplateParser()
        parsed = None

        if template.template_aasx:
            try:
                parsed = parser.parse_aasx(
                    template.template_aasx,
                    expected_semantic_id=descriptor.semantic_id,
                )
            except Exception as exc:
                logger.warning(
                    "template_aasx_parse_failed",
                    template_key=template.template_key,
                    version=template.idta_version,
                    error=str(exc),
                )

        if parsed is None:
            try:
                payload = json.dumps(template.template_json).encode()
                parsed = parser.parse_json(
                    payload,
                    expected_semantic_id=descriptor.semantic_id,
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(
                    "template_json_parse_failed",
                    template_key=template.template_key,
                    version=template.idta_version,
                    error=str(exc),
                )
                raise TemplateParseError(
                    template.template_key,
                    template.idta_version,
                    "Template parse failed; unable to load BaSyx object model.",
                ) from exc

        builder = TemplateDefinitionBuilder()
        return builder.build_definition(
            template_key=template.template_key,
            parsed=parsed,
            idta_version=template.idta_version,
            semantic_id=template.semantic_id,
        )

    async def refresh_all_templates(self) -> list[Template]:
        """
        Refresh all DPP4.0 templates from IDTA repository.

        Used during initial setup and scheduled template updates.
        """
        templates: list[Template] = []

        for template_key in list_template_keys():
            try:
                template = await self.refresh_template(template_key)
                templates.append(template)
            except Exception as e:
                logger.error(
                    "template_refresh_failed",
                    template_key=template_key,
                    error=str(e),
                )

        await self._session.commit()
        return templates

    def _build_template_url(
        self, descriptor: TemplateDescriptor, version: str, file_kind: str = "aasx"
    ) -> str:
        """
        Build a fallback download URL for an IDTA template.

        This is kept for backward compatibility and is used only if the
        GitHub API resolution fails.
        """
        base_url = self._settings.idta_templates_base_url.rstrip("/")
        folder_name = descriptor.repo_folder
        major, minor, patch = self._split_version(version)
        if file_kind == "json":
            file_pattern = descriptor.resolve_json_pattern()
        else:
            file_pattern = descriptor.aasx_pattern

        file_name = file_pattern.format(major=major, minor=minor, patch=patch)

        # Encode each path segment to safely handle spaces/special characters
        segments = [
            base_url,
            quote(folder_name),
            quote(major),
            quote(minor),
            quote(patch),
            quote(file_name),
        ]
        return "/".join(segments)

    def _split_version(self, version: str) -> tuple[str, str, str]:
        parts = version.split(".")
        if len(parts) >= 3:
            return parts[0], parts[1], parts[2]
        if len(parts) == 2:
            return parts[0], parts[1], "0"
        return parts[0], "0", "0"

    def _github_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "mini-dpp-platform",
        }
        token = self._settings.idta_templates_github_token
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _resolve_template_assets(
        self, descriptor: TemplateDescriptor, version: str
    ) -> tuple[str | None, str | None]:
        """
        Resolve template JSON and AASX URLs using the GitHub contents API.

        The IDTA repository uses a version directory structure (major/minor/patch)
        with multiple files per folder, so we dynamically select the best matches.
        """
        folder_name = descriptor.repo_folder

        major, minor, patch = self._split_version(version)
        api_base = self._settings.idta_templates_repo_api_url.rstrip("/")
        ref = self._settings.idta_templates_repo_ref
        api_url = f"{api_base}/{folder_name}/{major}/{minor}/{patch}?ref={ref}"

        try:
            client = await self._get_http_client()
            response = await client.get(api_url, headers=self._github_headers())
            response.raise_for_status()
            payload = response.json()
        except Exception as e:
            logger.warning(
                "template_resolve_failed",
                template_key=descriptor.key,
                version=version,
                error=str(e),
            )
            return None, None

        if not isinstance(payload, list):
            logger.warning(
                "template_resolve_unexpected_payload",
                template_key=descriptor.key,
                version=version,
            )
            return None, None

        json_files = [item for item in payload if str(item.get("name", "")).endswith(".json")]
        aasx_files = [item for item in payload if str(item.get("name", "")).endswith(".aasx")]

        expected_json = self._expected_template_filename(descriptor, version, file_kind="json")
        expected_aasx = self._expected_template_filename(descriptor, version, file_kind="aasx")

        json_url = self._select_template_file(
            json_files, prefer_kind="json", expected_name=expected_json
        )
        aasx_url = self._select_template_file(
            aasx_files, prefer_kind="aasx", expected_name=expected_aasx
        )

        if not json_url and not aasx_url:
            logger.warning(
                "template_assets_missing",
                template_key=descriptor.key,
                version=version,
            )

        return json_url, aasx_url

    def _select_template_file(
        self,
        files: list[dict[str, Any]],
        prefer_kind: str,
        expected_name: str | None = None,
    ) -> str | None:
        if not files:
            return None

        expected = expected_name.lower() if expected_name else None
        if expected:
            for file_item in files:
                name = str(file_item.get("name", ""))
                if name.lower() == expected:
                    return cast(str | None, file_item.get("download_url"))

        def score(file_item: dict[str, Any]) -> tuple[int, str]:
            name = str(file_item.get("name", ""))
            lowered = name.lower()
            points = 0

            if "template" in lowered:
                points += 5
            if "sample" in lowered or "example" in lowered:
                points -= 6
            if "schema" in lowered:
                points -= 8
            if "foraasmetamodel" in lowered:
                points -= 3
            if prefer_kind == "json" and "submodel" in lowered:
                points += 1
            if prefer_kind == "aasx" and "aasx" in lowered:
                points += 1

            # Secondary sort by name to keep selection deterministic.
            return (points, lowered)

        files_sorted = sorted(files, key=score, reverse=True)
        chosen = files_sorted[0]
        return cast(str | None, chosen.get("download_url"))

    def _expected_template_filename(
        self, descriptor: TemplateDescriptor, version: str, file_kind: str
    ) -> str:
        major, minor, patch = self._split_version(version)
        if file_kind == "json":
            pattern = descriptor.resolve_json_pattern()
        else:
            pattern = descriptor.aasx_pattern
        return pattern.format(major=major, minor=minor, patch=patch)

    def _normalize_template_json(
        self, payload: dict[str, Any], template_key: str
    ) -> dict[str, Any]:
        """
        Normalize template JSON payload into AAS Environment format.

        Supports full AAS environments or standalone submodel JSON files.
        """
        if not isinstance(payload, dict):
            raise ValueError("template_json_invalid")

        if "submodels" in payload or "assetAdministrationShells" in payload:
            return self._normalize_aas_environment(payload)

        submodel = payload.get("submodel") if isinstance(payload.get("submodel"), dict) else payload

        if not isinstance(submodel, dict):
            raise ValueError("template_json_missing_submodel")

        if not submodel.get("idShort"):
            submodel["idShort"] = template_key.replace("-", "_").title().replace("_", "")

        environment = {
            "assetAdministrationShells": [],
            "submodels": [submodel],
            "conceptDescriptions": payload.get("conceptDescriptions", []),
        }

        return self._normalize_aas_environment(environment)

    def _extract_aas_environment(self, aasx_bytes: bytes) -> dict[str, Any]:
        """
        Extract and normalize AAS Environment from an AASX package.
        """
        aas_env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [],
            "conceptDescriptions": [],
        }

        with zipfile.ZipFile(io.BytesIO(aasx_bytes), "r") as zf:
            for name in zf.namelist():
                if name.endswith(".json") and "aas" in name.lower():
                    with zf.open(name) as f:
                        content = json.load(f)
                        if "assetAdministrationShells" in content:
                            aas_env["assetAdministrationShells"].extend(
                                content["assetAdministrationShells"]
                            )
                        if "submodels" in content:
                            aas_env["submodels"].extend(content["submodels"])
                        if "conceptDescriptions" in content:
                            aas_env["conceptDescriptions"].extend(content["conceptDescriptions"])

        if not aas_env["submodels"]:
            aas_env = self._extract_from_xml(aasx_bytes)

        return self._normalize_aas_environment(aas_env)

    def _extract_from_xml(self, aasx_bytes: bytes) -> dict[str, Any]:
        """
        Extract AAS Environment from XML inside AASX.
        """
        import xmltodict  # type: ignore[import-untyped]

        aas_env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [],
            "conceptDescriptions": [],
        }

        with zipfile.ZipFile(io.BytesIO(aasx_bytes), "r") as zf:
            for name in zf.namelist():
                if name.endswith(".xml") and (
                    "aas" in name.lower() or "environment" in name.lower()
                ):
                    with zf.open(name) as f:
                        xml_content = f.read()
                        parsed = xmltodict.parse(xml_content)
                        env_data = parsed.get("aas:aasenv", parsed.get("environment", {}))

                        shells = env_data.get("aas:assetAdministrationShells")
                        if shells:
                            if isinstance(shells, dict):
                                shells = [shells]
                            aas_env["assetAdministrationShells"].extend(shells)

                        submodels = env_data.get("aas:submodels")
                        if submodels:
                            if isinstance(submodels, dict):
                                submodels = [submodels]
                            aas_env["submodels"].extend(submodels)

        return aas_env

    def _normalize_aas_environment(self, aas_env: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize AAS Environment to canonical JSON format.
        """

        def sort_dict(value: Any) -> Any:
            if isinstance(value, dict):
                return {k: sort_dict(v) for k, v in sorted(value.items())}
            if isinstance(value, list):
                return [sort_dict(item) for item in value]
            return value

        normalized = cast(dict[str, Any], sort_dict(aas_env))
        normalized.setdefault("assetAdministrationShells", [])
        normalized.setdefault("submodels", [])
        normalized.setdefault("conceptDescriptions", [])
        return normalized

    def generate_ui_schema(self, template: Template) -> dict[str, Any]:
        """
        Generate a UI schema from a template for form rendering.

        Converts AAS submodel structure to a form-compatible schema
        that the frontend can use to dynamically render editing forms.
        """
        submodels = template.template_json.get("submodels", [])

        if not submodels:
            return {"type": "object", "properties": {}}

        # Take the first submodel (templates typically have one)
        submodel = submodels[0]

        return self._submodel_to_ui_schema(submodel)

    def _submodel_to_ui_schema(self, submodel: dict[str, Any]) -> dict[str, Any]:
        """
        Convert a submodel to JSON Schema compatible UI schema.

        Handles SubmodelElementCollection, Property, MultiLanguageProperty,
        Range, Blob, File, and other AAS element types.
        """
        schema: dict[str, Any] = {
            "type": "object",
            "title": submodel.get("idShort", "Submodel"),
            "description": self._get_description(submodel),
            "properties": {},
            "required": [],
        }

        elements = submodel.get("submodelElements", [])

        for element in elements:
            id_short = element.get("idShort", "")

            if not id_short:
                continue

            if self._is_required(element):
                schema["required"].append(id_short)

            schema["properties"][id_short] = self._element_to_schema(element)

        return schema

    def _collection_to_schema(self, element: dict[str, Any]) -> dict[str, Any]:
        """Convert SubmodelElementCollection to nested object schema."""
        nested_elements = element.get("value", [])

        nested_schema: dict[str, Any] = {
            "type": "object",
            "title": element.get("idShort", ""),
            "description": self._get_description(element),
            "properties": {},
            "required": [],
        }

        for nested in nested_elements:
            nested_id = nested.get("idShort", "")

            if not nested_id:
                continue

            if self._is_required(nested):
                nested_schema["required"].append(nested_id)

            nested_schema["properties"][nested_id] = self._element_to_schema(nested)

        return nested_schema

    def _list_to_schema(self, element: dict[str, Any]) -> dict[str, Any]:
        """Convert SubmodelElementList to array schema."""
        items = element.get("value", [])
        if items:
            item_schema = self._element_to_schema(items[0])
        else:
            item_template = self._build_list_item_template(element)
            if item_template:
                item_schema = self._element_to_schema(item_template)
            else:
                item_schema = {"type": "string"}

        schema: dict[str, Any] = {
            "type": "array",
            "title": element.get("idShort", ""),
            "description": self._get_description(element),
            "items": item_schema,
        }

        qualifiers = parse_smt_qualifiers(element.get("qualifiers", []))
        if qualifiers.cardinality == "OneToMany":
            schema["minItems"] = 1
        elif qualifiers.cardinality == "ZeroToMany":
            schema["minItems"] = 0

        return schema

    def _property_to_schema(self, element: dict[str, Any]) -> dict[str, Any]:
        """Convert Property to typed schema property."""
        value_type = element.get("valueType", "xs:string")

        # Map AAS value types to JSON Schema types
        type_mapping: dict[str, str] = {
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

        json_type = type_mapping.get(value_type, "string")

        property_schema: dict[str, Any] = {
            "type": json_type,
            "title": element.get("idShort", ""),
            "description": self._get_description(element),
        }

        # Add format hints
        if value_type in ("xs:date", "xs:dateTime"):
            property_schema["format"] = "date-time" if "Time" in value_type else "date"
        elif value_type == "xs:anyURI":
            property_schema["format"] = "uri"

        # Add semantic ID as custom property
        if "semanticId" in element:
            property_schema["x-semantic-id"] = element["semanticId"]

        return property_schema

    def _mlp_to_schema(self, element: dict[str, Any]) -> dict[str, Any]:
        """Convert MultiLanguageProperty to object with language keys."""
        return {
            "type": "object",
            "title": element.get("idShort", ""),
            "description": self._get_description(element),
            "additionalProperties": {
                "type": "string",
            },
            "x-multi-language": True,
        }

    def _range_to_schema(self, element: dict[str, Any]) -> dict[str, Any]:
        """Convert Range to object with min/max properties."""
        return {
            "type": "object",
            "title": element.get("idShort", ""),
            "description": self._get_description(element),
            "properties": {
                "min": {"type": "number"},
                "max": {"type": "number"},
            },
            "x-range": True,
        }

    def _file_to_schema(self, element: dict[str, Any]) -> dict[str, Any]:
        """Convert File element to file upload schema."""
        return {
            "type": "object",
            "title": element.get("idShort", ""),
            "description": self._get_description(element),
            "properties": {
                "contentType": {"type": "string"},
                "value": {"type": "string", "format": "uri"},
            },
            "x-file-upload": True,
        }

    def _blob_to_schema(self, element: dict[str, Any]) -> dict[str, Any]:
        """Convert Blob element to base64 data schema."""
        return {
            "type": "object",
            "title": element.get("idShort", ""),
            "description": self._get_description(element),
            "properties": {
                "contentType": {"type": "string"},
                "value": {"type": "string", "contentEncoding": "base64"},
            },
            "x-blob": True,
            "x-readonly": True,
        }

    def _reference_to_schema(self, element: dict[str, Any]) -> dict[str, Any]:
        """Convert ReferenceElement to reference schema."""
        return {
            "type": "object",
            "title": element.get("idShort", ""),
            "description": self._get_description(element),
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

    def _entity_to_schema(self, element: dict[str, Any]) -> dict[str, Any]:
        """Convert Entity element to editable schema."""
        statements = element.get("statements", [])
        statements_schema: dict[str, Any] = {
            "type": "object",
            "title": "Statements",
            "properties": {},
        }

        for statement in statements:
            statement_id = statement.get("idShort", "")
            if not statement_id:
                continue
            statements_schema["properties"][statement_id] = self._element_to_schema(statement)

        return {
            "type": "object",
            "title": element.get("idShort", ""),
            "description": self._get_description(element),
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

    def _relationship_to_schema(self, element: dict[str, Any]) -> dict[str, Any]:
        """Convert RelationshipElement to reference pair schema."""
        return {
            "type": "object",
            "title": element.get("idShort", ""),
            "description": self._get_description(element),
            "properties": {
                "first": self._reference_to_schema({"idShort": "First"}),
                "second": self._reference_to_schema({"idShort": "Second"}),
            },
            "x-relationship": True,
        }

    def _annotated_relationship_to_schema(self, element: dict[str, Any]) -> dict[str, Any]:
        """Convert AnnotatedRelationshipElement to schema."""
        annotations = element.get("annotations", [])
        annotations_schema: dict[str, Any] = {
            "type": "object",
            "title": "Annotations",
            "properties": {},
        }

        for annotation in annotations:
            annotation_id = annotation.get("idShort", "")
            if not annotation_id:
                continue
            annotations_schema["properties"][annotation_id] = self._element_to_schema(annotation)

        return {
            "type": "object",
            "title": element.get("idShort", ""),
            "description": self._get_description(element),
            "properties": {
                "first": self._reference_to_schema({"idShort": "First"}),
                "second": self._reference_to_schema({"idShort": "Second"}),
                "annotations": annotations_schema,
            },
            "x-annotated-relationship": True,
        }

    def _operation_to_schema(self, element: dict[str, Any]) -> dict[str, Any]:
        """Convert Operation to read-only schema placeholder."""
        return {
            "type": "object",
            "title": element.get("idShort", ""),
            "description": self._get_description(element),
            "properties": {},
            "x-readonly": True,
        }

    def _capability_to_schema(self, element: dict[str, Any]) -> dict[str, Any]:
        """Convert Capability to read-only schema placeholder."""
        return {
            "type": "object",
            "title": element.get("idShort", ""),
            "description": self._get_description(element),
            "properties": {},
            "x-readonly": True,
        }

    def _basic_event_to_schema(self, element: dict[str, Any]) -> dict[str, Any]:
        """Convert BasicEventElement to read-only schema placeholder."""
        return {
            "type": "object",
            "title": element.get("idShort", ""),
            "description": self._get_description(element),
            "properties": {},
            "x-readonly": True,
        }

    def _build_list_item_template(self, element: dict[str, Any]) -> dict[str, Any] | None:
        type_value = element.get("typeValueListElement")
        if isinstance(type_value, dict):
            type_value = type_value.get("name")
        value_type = element.get("valueTypeListElement")

        if not type_value:
            return None

        template: dict[str, Any] = {
            "idShort": "Item",
            "modelType": {"name": type_value},
        }

        if value_type:
            template["valueType"] = value_type

        return template

    def _element_to_schema(self, element: dict[str, Any]) -> dict[str, Any]:
        model_type = element.get("modelType", {})
        if isinstance(model_type, dict):
            element_type = model_type.get("name", "Property")
        elif isinstance(model_type, str):
            element_type = model_type
        else:
            element_type = "Property"

        if element_type == "SubmodelElementCollection":
            schema = self._collection_to_schema(element)
        elif element_type == "SubmodelElementList":
            schema = self._list_to_schema(element)
        elif element_type == "Property":
            schema = self._property_to_schema(element)
        elif element_type == "MultiLanguageProperty":
            schema = self._mlp_to_schema(element)
        elif element_type == "Range":
            schema = self._range_to_schema(element)
        elif element_type == "File":
            schema = self._file_to_schema(element)
        elif element_type == "Blob":
            schema = self._blob_to_schema(element)
        elif element_type == "ReferenceElement":
            schema = self._reference_to_schema(element)
        elif element_type == "Entity":
            schema = self._entity_to_schema(element)
        elif element_type == "RelationshipElement":
            schema = self._relationship_to_schema(element)
        elif element_type == "AnnotatedRelationshipElement":
            schema = self._annotated_relationship_to_schema(element)
        elif element_type == "Operation":
            schema = self._operation_to_schema(element)
        elif element_type == "Capability":
            schema = self._capability_to_schema(element)
        elif element_type == "BasicEventElement":
            schema = self._basic_event_to_schema(element)
        else:
            schema = {
                "type": "string",
                "title": element.get("idShort", ""),
            }

        qualifiers = parse_smt_qualifiers(element.get("qualifiers", []))
        return self._apply_qualifiers(schema, qualifiers)

    def _is_required(self, element: dict[str, Any]) -> bool:
        qualifiers = parse_smt_qualifiers(element.get("qualifiers", []))
        return qualifiers.cardinality in {"One", "OneToMany"}

    def _apply_qualifiers(self, schema: dict[str, Any], qualifiers: Any) -> dict[str, Any]:
        if qualifiers.cardinality:
            schema["x-cardinality"] = qualifiers.cardinality

        if qualifiers.form_title:
            schema["title"] = qualifiers.form_title
            schema["x-form-title"] = qualifiers.form_title

        if qualifiers.form_info:
            if not schema.get("description"):
                schema["description"] = qualifiers.form_info
            schema["x-form-info"] = qualifiers.form_info

        if qualifiers.form_url:
            schema["x-form-url"] = qualifiers.form_url

        if qualifiers.form_choices:
            schema["x-form-choices"] = qualifiers.form_choices
            if schema.get("type") == "string" and not schema.get("enum"):
                schema["enum"] = qualifiers.form_choices

        if qualifiers.default_value is not None and schema.get("type"):
            schema["default"] = self._coerce_value(qualifiers.default_value, schema["type"])

        if qualifiers.example_value is not None and schema.get("type"):
            schema["examples"] = [self._coerce_value(qualifiers.example_value, schema["type"])]

        if qualifiers.allowed_value_regex:
            schema["pattern"] = qualifiers.allowed_value_regex
            schema["x-allowed-value"] = qualifiers.allowed_value_regex

        if qualifiers.allowed_range:
            parsed = parse_allowed_range(qualifiers.allowed_range)
            if parsed:
                schema["minimum"] = parsed[0]
                schema["maximum"] = parsed[1]
            else:
                schema["x-allowed-range"] = qualifiers.allowed_range

        if qualifiers.required_lang:
            schema["x-required-languages"] = sorted(set(qualifiers.required_lang))

        if qualifiers.either_or:
            schema["x-either-or"] = qualifiers.either_or

        if qualifiers.access_mode:
            access_mode = qualifiers.access_mode.strip().lower()
            if access_mode in {"readonly", "read-only", "read_only"}:
                schema["readOnly"] = True
                schema["x-readonly"] = True
            if access_mode in {"writeonly", "write-only", "write_only"}:
                schema["writeOnly"] = True

        if qualifiers.allowed_id_short:
            schema["x-allowed-id-short"] = qualifiers.allowed_id_short

        if qualifiers.edit_id_short is not None:
            schema["x-edit-id-short"] = qualifiers.edit_id_short

        if qualifiers.naming:
            schema["x-naming"] = qualifiers.naming

        return schema

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
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return value

    def _get_description(self, element: dict[str, Any]) -> str:
        """Extract description from AAS element."""
        descriptions = element.get("description", [])

        if isinstance(descriptions, list):
            # Find English description first
            for desc in descriptions:
                if desc.get("language", "").startswith("en"):
                    return str(desc.get("text", ""))
            # Fallback to first available
            if descriptions:
                return str(descriptions[0].get("text", ""))

        return ""
