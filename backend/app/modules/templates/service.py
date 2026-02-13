"""
Template Registry Service for IDTA Submodel Templates.
Handles fetching, parsing, caching, and versioning of DPP4.0 templates.
"""

import io
import json
import re
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast
from urllib.parse import quote, urlparse

import httpx
from basyx.aas import model
from basyx.aas.adapter import aasx as basyx_aasx
from basyx.aas.adapter import json as basyx_json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import Template
from app.modules.aas.references import reference_to_str
from app.modules.templates.basyx_parser import BasyxTemplateParser
from app.modules.templates.catalog import (
    TemplateDescriptor,
    get_template_descriptor,
    list_template_keys,
)
from app.modules.templates.definition import TemplateDefinitionBuilder
from app.modules.templates.dropin_resolver import TemplateDropInResolver
from app.modules.templates.schema_from_definition import DefinitionToSchemaConverter

logger = get_logger(__name__)

SELECTION_STRATEGY = "deterministic_v2"

# Module-level definition cache keyed by (template_key, version, source_file_sha).
# Definitions are deterministic given the same template data, so caching across
# requests is safe.  Bounded to 32 entries (~6 templates × a few versions).
_definition_cache: dict[tuple[str, str, str | None], dict[str, Any]] = {}
_DEFINITION_CACHE_MAX = 32


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


@dataclass(frozen=True)
class TemplateRefreshResult:
    template_key: str
    status: Literal["ok", "failed", "skipped"]
    support_status: str
    error: str | None = None
    idta_version: str | None = None
    resolved_version: str | None = None
    source_metadata: dict[str, Any] | None = None
    selection_diagnostics: dict[str, Any] | None = None


@dataclass(frozen=True)
class TemplateCandidateResolution:
    """Resolved upstream candidate with parsed AAS environment."""

    asset: dict[str, Any] | None
    kind: Literal["json", "aasx"]
    aas_env_json: dict[str, Any]
    aasx_bytes: bytes | None
    source_url: str
    selected_submodel_semantic_id: str | None
    selection_strategy: str


class TemplateRegistryService:
    """
    Manages IDTA submodel templates for DPP creation and editing.

    Provides template fetching, caching, normalization, and version management.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    async def get_all_templates(self) -> list[Template]:
        """
        Get all registered templates from the database.

        Returns latest version per template key for consistent display.
        """
        result = await self._session.execute(
            select(Template).order_by(
                Template.template_key.asc(),
                Template.fetched_at.desc(),
                Template.idta_version.desc(),
            )
        )
        latest_by_key: dict[str, Template] = {}
        for template in result.scalars():
            if template.template_key not in latest_by_key:
                latest_by_key[template.template_key] = template
        return [latest_by_key[key] for key in sorted(latest_by_key.keys())]

    async def get_template(
        self,
        template_key: str,
        version: str | None = None,
    ) -> Template | None:
        """
        Get a specific template by key and optional version.

        If version is not specified, returns the latest stored version.
        """
        if version is None:
            result = await self._session.execute(
                select(Template)
                .where(Template.template_key == template_key)
                .order_by(Template.fetched_at.desc(), Template.idta_version.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

        result = await self._session.execute(
            select(Template).where(
                Template.template_key == template_key,
                Template.idta_version == version,
            )
        )
        return result.scalar_one_or_none()

    async def list_template_versions(self, template_key: str) -> list[dict[str, Any]]:
        """
        List all stored versions for a template, indicating the latest stored default.

        Returns a list of dicts with version, is_default, and created_at.
        """
        result = await self._session.execute(
            select(Template.idta_version, Template.fetched_at).where(
                Template.template_key == template_key
            )
        )
        rows = list(result.all())
        rows.sort(key=lambda row: self._version_key(str(row.idta_version)), reverse=True)
        latest = rows[0].idta_version if rows else None
        return [
            {
                "version": row.idta_version,
                "is_default": row.idta_version == latest,
                "created_at": row.fetched_at.isoformat() if row.fetched_at else None,
            }
            for row in rows
        ]

    async def refresh_template(self, template_key: str) -> Template:
        """
        Fetch or update a template from IDTA repository.

        Downloads the AASX package, extracts and normalizes the AAS environment,
        and stores both the original package and normalized JSON.
        """
        descriptor = get_template_descriptor(template_key)
        if descriptor is None:
            raise ValueError(f"Unknown template key: {template_key}")
        if not descriptor.refresh_enabled:
            raise ValueError(
                f"Template '{template_key}' is marked as {descriptor.support_status} and cannot "
                "be refreshed from the upstream repository."
            )

        version = await self._resolve_template_version(descriptor)

        # Resolve source URLs based on IDTA repo structure
        (
            json_asset,
            aasx_asset,
            json_candidates,
            aasx_candidates,
        ) = await self._resolve_template_assets(descriptor, version)
        json_url = cast(str | None, json_asset.get("download_url")) if json_asset else None
        aasx_url = cast(str | None, aasx_asset.get("download_url")) if aasx_asset else None

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

        candidate_resolution: TemplateCandidateResolution | None = None
        selection_diagnostics: dict[str, Any] = {
            "candidate_files": {
                "json": self._candidate_snapshot(json_candidates),
                "aasx": self._candidate_snapshot(aasx_candidates),
            },
            "selection_strategy": None,
            "selected_file": None,
            "selected_submodel_semantic_id": None,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            if json_candidates:
                candidate_resolution = await self._resolve_candidate_by_semantic(
                    client=client,
                    template_key=template_key,
                    descriptor=descriptor,
                    version=version,
                    file_kind="json",
                    candidates=json_candidates,
                )

            if candidate_resolution is None and aasx_candidates:
                candidate_resolution = await self._resolve_candidate_by_semantic(
                    client=client,
                    template_key=template_key,
                    descriptor=descriptor,
                    version=version,
                    file_kind="aasx",
                    candidates=aasx_candidates,
                )

            if candidate_resolution is None and json_url:
                candidate_resolution = await self._resolve_direct_url_candidate(
                    client=client,
                    template_key=template_key,
                    descriptor=descriptor,
                    version=version,
                    file_kind="json",
                    url=json_url,
                )

            if candidate_resolution is None and aasx_url:
                candidate_resolution = await self._resolve_direct_url_candidate(
                    client=client,
                    template_key=template_key,
                    descriptor=descriptor,
                    version=version,
                    file_kind="aasx",
                    url=aasx_url,
                )

        if candidate_resolution is None:
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

        aas_env_json = candidate_resolution.aas_env_json
        template_aasx = candidate_resolution.aasx_bytes
        source_url = candidate_resolution.source_url
        source_kind = candidate_resolution.kind
        source_file_path = (
            cast(str | None, candidate_resolution.asset.get("path"))
            if candidate_resolution.asset
            else None
        )
        source_file_sha = (
            cast(str | None, candidate_resolution.asset.get("sha"))
            if candidate_resolution.asset
            else None
        )
        selection_strategy = candidate_resolution.selection_strategy
        selection_diagnostics["selection_strategy"] = selection_strategy
        selection_diagnostics["selected_submodel_semantic_id"] = (
            candidate_resolution.selected_submodel_semantic_id
        )
        selection_diagnostics["selected_file"] = {
            "kind": source_kind,
            "url": source_url,
            "path": source_file_path,
            "sha": source_file_sha,
            "name": (
                cast(str | None, candidate_resolution.asset.get("name"))
                if candidate_resolution.asset
                else None
            ),
        }

        semantic_id = descriptor.semantic_id

        # Upsert template record
        existing = await self.get_template(template_key, version)

        if existing:
            existing.template_json = aas_env_json
            if template_aasx is not None:
                existing.template_aasx = template_aasx
            if source_url is not None:
                existing.source_url = source_url
            existing.resolved_version = version
            existing.source_repo_ref = self._settings.idta_templates_repo_ref
            existing.source_file_path = source_file_path
            existing.source_file_sha = source_file_sha
            existing.source_kind = source_kind
            existing.selection_strategy = selection_strategy
            existing.fetched_at = datetime.now(UTC)
            template = existing
        else:
            template = Template(
                template_key=template_key,
                idta_version=version,
                resolved_version=version,
                semantic_id=semantic_id,
                source_url=source_url or (json_url or aasx_url or ""),
                source_repo_ref=self._settings.idta_templates_repo_ref,
                source_file_path=source_file_path,
                source_file_sha=source_file_sha,
                source_kind=source_kind,
                selection_strategy=selection_strategy,
                template_aasx=template_aasx,
                template_json=aas_env_json,
                fetched_at=datetime.now(UTC),
            )
            self._session.add(template)

        await self._session.flush()

        # Invalidate cached definition for this template
        _definition_cache.pop((template_key, version, source_file_sha), None)

        logger.info(
            "template_refreshed",
            template_key=template_key,
            version=version,
            submodel_count=len(aas_env_json.get("submodels", [])),
        )
        template._selection_diagnostics = selection_diagnostics  # type: ignore[attr-defined]

        return template

    def generate_template_definition(
        self,
        template: Template,
        template_lookup: Mapping[str, Template] | None = None,
    ) -> dict[str, Any]:
        return self._generate_template_definition(template, template_lookup=template_lookup)

    def _generate_template_definition(
        self,
        template: Template,
        template_lookup: Mapping[str, Template] | None,
    ) -> dict[str, Any]:
        use_cache = not template_lookup
        cache_key = (template.template_key, template.idta_version, template.source_file_sha)
        if use_cache:
            cached = _definition_cache.get(cache_key)
            if cached is not None:
                return cached

        descriptor = get_template_descriptor(template.template_key)
        if descriptor is None:
            raise ValueError(f"Unknown template key: {template.template_key}")

        parsed = self._parse_template_model(template, descriptor.semantic_id)
        resolution_by_element_id: dict[int, dict[str, Any]] = {}
        if template_lookup:
            parsed_by_template: dict[str, Any] = {}

            def source_provider(source_template_key: str) -> model.Submodel | None:
                source_template = template_lookup.get(source_template_key)
                if source_template is None:
                    return None
                if source_template_key not in parsed_by_template:
                    source_descriptor = get_template_descriptor(source_template_key)
                    expected_semantic_id = (
                        source_descriptor.semantic_id
                        if source_descriptor is not None
                        else source_template.semantic_id
                    )
                    parsed_by_template[source_template_key] = self._parse_template_model(
                        source_template,
                        expected_semantic_id,
                    )
                return cast(model.Submodel, parsed_by_template[source_template_key].submodel)

            resolution_by_element_id = TemplateDropInResolver().resolve(
                template_key=template.template_key,
                submodel=parsed.submodel,
                source_provider=source_provider,
            )

        builder = TemplateDefinitionBuilder(resolution_by_element_id=resolution_by_element_id)
        definition = builder.build_definition(
            template_key=template.template_key,
            parsed=parsed,
            idta_version=template.idta_version,
            semantic_id=template.semantic_id,
        )

        if use_cache:
            # Evict oldest entry if cache is full
            if len(_definition_cache) >= _DEFINITION_CACHE_MAX:
                oldest_key = next(iter(_definition_cache))
                del _definition_cache[oldest_key]
            _definition_cache[cache_key] = definition

        return definition

    def _parse_template_model(
        self,
        template: Template,
        expected_semantic_id: str | None,
    ) -> Any:
        parser = BasyxTemplateParser()
        parsed = None

        if template.template_aasx:
            try:
                parsed = parser.parse_aasx(
                    template.template_aasx,
                    expected_semantic_id=expected_semantic_id,
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
                    expected_semantic_id=expected_semantic_id,
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
        return parsed

    async def refresh_all_templates(self) -> tuple[list[Template], list[TemplateRefreshResult]]:
        """
        Refresh all DPP4.0 templates from IDTA repository.

        Used during initial setup and scheduled template updates.
        """
        templates: list[Template] = []
        results: list[TemplateRefreshResult] = []

        for template_key in list_template_keys():
            descriptor = get_template_descriptor(template_key)
            support_status = descriptor.support_status if descriptor else "supported"

            if descriptor is not None and not descriptor.refresh_enabled:
                message = (
                    f"Template is marked as {descriptor.support_status}; upstream source currently "
                    "unavailable."
                )
                logger.info(
                    "template_refresh_skipped",
                    template_key=template_key,
                    support_status=descriptor.support_status,
                    reason=message,
                )
                results.append(
                    TemplateRefreshResult(
                        template_key=template_key,
                        status="skipped",
                        support_status=support_status,
                        error=message,
                    )
                )
                continue

            try:
                template = await self.refresh_template(template_key)
                templates.append(template)
                results.append(
                    TemplateRefreshResult(
                        template_key=template_key,
                        status="ok",
                        support_status=support_status,
                        idta_version=template.idta_version,
                        resolved_version=template.resolved_version or template.idta_version,
                        source_metadata=self._source_metadata(template),
                        selection_diagnostics=getattr(template, "_selection_diagnostics", None),
                    )
                )
            except Exception as e:
                logger.error(
                    "template_refresh_failed",
                    template_key=template_key,
                    error=str(e),
                )
                results.append(
                    TemplateRefreshResult(
                        template_key=template_key,
                        status="failed",
                        support_status=support_status,
                        error=str(e),
                    )
                )

        await self._session.commit()
        return templates, results

    async def _resolve_template_version(self, descriptor: TemplateDescriptor) -> str:
        policy = self._settings.template_version_resolution_policy
        baseline_major, baseline_minor = self._baseline_for_template(descriptor)

        if policy != "latest_patch":
            legacy = self._settings.template_versions.get(descriptor.key)
            if legacy:
                return legacy
            return f"{baseline_major}.{baseline_minor}.0"

        patches = await self._list_available_patches(
            descriptor=descriptor,
            major=baseline_major,
            minor=baseline_minor,
        )
        patches = sorted(set(patches))
        if not patches:
            legacy = self._settings.template_versions.get(descriptor.key)
            if legacy:
                return legacy
            return f"{baseline_major}.{baseline_minor}.0"
        return f"{baseline_major}.{baseline_minor}.{patches[-1]}"

    def _baseline_for_template(self, descriptor: TemplateDescriptor) -> tuple[int, int]:
        configured = self._settings.template_major_minor_baselines.get(descriptor.key, "")
        match = re.match(r"^\s*(\d+)\.(\d+)\s*$", configured)
        if match:
            return int(match.group(1)), int(match.group(2))
        return descriptor.baseline_major, descriptor.baseline_minor

    async def _list_available_patches(
        self,
        descriptor: TemplateDescriptor,
        major: int,
        minor: int,
    ) -> list[int]:
        api_base = self._settings.idta_templates_repo_api_url.rstrip("/")
        ref = self._settings.idta_templates_repo_ref
        api_url = f"{api_base}/{quote(descriptor.repo_folder)}/{major}/{minor}?ref={ref}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(api_url, headers=self._github_headers())
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            logger.warning(
                "template_patch_discovery_failed",
                template_key=descriptor.key,
                major=major,
                minor=minor,
                error=str(exc),
            )
            return []

        if not isinstance(payload, list):
            return []

        patches: list[int] = []
        for item in payload:
            if item.get("type") != "dir":
                continue
            name = str(item.get("name", "")).strip()
            if name.isdigit():
                patches.append(int(name))

        return sorted(set(patches))

    def _build_template_url(
        self, descriptor: TemplateDescriptor, version: str, file_kind: str = "aasx"
    ) -> str:
        """
        Build a fallback download URL for an IDTA template.

        This is kept for backward compatibility and is used only if the
        GitHub API resolution fails.
        """
        base_url = self._resolve_base_url().rstrip("/")
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

    def _resolve_base_url(self) -> str:
        base_url = self._settings.idta_templates_base_url.rstrip("/")
        ref = self._settings.idta_templates_repo_ref
        if not ref:
            return base_url

        parsed = urlparse(base_url)
        if parsed.netloc != "raw.githubusercontent.com":
            return base_url

        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 3 and parts[0] == "admin-shell-io" and parts[1] == "submodel-templates":
            parts[2] = ref
            return parsed._replace(path="/" + "/".join(parts)).geturl()

        return base_url

    def _split_version(self, version: str) -> tuple[str, str, str]:
        parts = version.split(".")
        if len(parts) >= 3:
            return parts[0], parts[1], parts[2]
        if len(parts) == 2:
            return parts[0], parts[1], "0"
        return parts[0], "0", "0"

    def _version_key(self, version: str) -> tuple[int, int, int]:
        major, minor, patch = self._split_version(version)
        try:
            return int(major), int(minor), int(patch)
        except ValueError:
            return 0, 0, 0

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
    ) -> tuple[
        dict[str, Any] | None,
        dict[str, Any] | None,
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
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
            async with httpx.AsyncClient(timeout=30.0) as client:
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
            return None, None, [], []

        if not isinstance(payload, list):
            logger.warning(
                "template_resolve_unexpected_payload",
                template_key=descriptor.key,
                version=version,
            )
            return None, None, [], []

        json_files = [
            item for item in payload if str(item.get("name", "")).lower().endswith(".json")
        ]
        aasx_files = [
            item for item in payload if str(item.get("name", "")).lower().endswith(".aasx")
        ]

        expected_json = self._expected_template_filename(descriptor, version, file_kind="json")
        expected_aasx = self._expected_template_filename(descriptor, version, file_kind="aasx")

        ranked_json = self._rank_template_files(
            json_files, prefer_kind="json", expected_name=expected_json
        )
        ranked_aasx = self._rank_template_files(
            aasx_files, prefer_kind="aasx", expected_name=expected_aasx
        )
        json_asset = ranked_json[0] if ranked_json else None
        aasx_asset = ranked_aasx[0] if ranked_aasx else None

        if not json_asset and not aasx_asset:
            logger.warning(
                "template_assets_missing",
                template_key=descriptor.key,
                version=version,
            )

        return json_asset, aasx_asset, ranked_json, ranked_aasx

    def _select_template_file(
        self,
        files: list[dict[str, Any]],
        prefer_kind: str,
        expected_name: str | None = None,
    ) -> dict[str, Any] | None:
        ranked = self._rank_template_files(
            files,
            prefer_kind=prefer_kind,
            expected_name=expected_name,
        )
        return ranked[0] if ranked else None

    def _rank_template_files(
        self,
        files: list[dict[str, Any]],
        *,
        prefer_kind: str,
        expected_name: str | None = None,
    ) -> list[dict[str, Any]]:
        if not files:
            return []

        expected = expected_name.lower() if expected_name else None

        def score(file_item: dict[str, Any]) -> tuple[int, int, int, str]:
            name = str(file_item.get("name", ""))
            lowered = name.lower()

            exact_match = 1 if expected and lowered == expected else 0
            template_points = 1 if "template" in lowered else 0
            kind_points = 1 if prefer_kind in lowered else 0
            penalty = 0
            if "sample" in lowered or "example" in lowered:
                penalty += 3
            if "schema" in lowered:
                penalty += 3
            if "foraasmetamodel" in lowered:
                penalty += 1
            if prefer_kind == "json" and "submodel" in lowered:
                template_points += 1

            # Higher is better except penalty; lexicographic tie-break keeps deterministic output.
            return (exact_match, template_points, kind_points - penalty, lowered)

        return sorted(files, key=score, reverse=True)

    def _candidate_snapshot(self, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        snapshot = [
            {
                "name": str(item.get("name") or ""),
                "path": str(item.get("path") or ""),
                "sha": str(item.get("sha") or ""),
            }
            for item in files
        ]
        snapshot.sort(key=lambda item: (item["name"], item["path"], item["sha"]))
        return snapshot

    async def _resolve_candidate_by_semantic(
        self,
        *,
        client: httpx.AsyncClient,
        template_key: str,
        descriptor: TemplateDescriptor,
        version: str,
        file_kind: Literal["json", "aasx"],
        candidates: list[dict[str, Any]],
    ) -> TemplateCandidateResolution | None:
        parser = BasyxTemplateParser()
        matches: list[TemplateCandidateResolution] = []
        parseable_fallbacks: list[TemplateCandidateResolution] = []

        for asset in candidates:
            url = cast(str | None, asset.get("download_url"))
            if not url:
                continue

            try:
                response = await client.get(url)
                response.raise_for_status()
            except Exception as exc:
                logger.warning(
                    "template_candidate_fetch_failed",
                    template_key=template_key,
                    version=version,
                    file_kind=file_kind,
                    source_url=url,
                    error=str(exc),
                )
                continue

            if file_kind == "json":
                try:
                    payload = response.json()
                    aas_env_json = self._normalize_template_json(payload, template_key)
                    if not aas_env_json.get("submodels"):
                        continue
                    parsed = parser.parse_json(
                        json.dumps(aas_env_json).encode("utf-8"),
                        expected_semantic_id=descriptor.semantic_id,
                    )
                    matches.append(
                        TemplateCandidateResolution(
                            asset=asset,
                            kind="json",
                            aas_env_json=aas_env_json,
                            aasx_bytes=None,
                            source_url=url,
                            selected_submodel_semantic_id=reference_to_str(
                                parsed.submodel.semantic_id
                            ),
                            selection_strategy=SELECTION_STRATEGY,
                        )
                    )
                    continue
                except Exception:
                    pass

                try:
                    # Fallback path for unique-candidate selection when semantic matching fails.
                    payload = response.json()
                    aas_env_json = self._normalize_template_json(payload, template_key)
                    parsed = parser.parse_json(json.dumps(aas_env_json).encode("utf-8"))
                    parseable_fallbacks.append(
                        TemplateCandidateResolution(
                            asset=asset,
                            kind="json",
                            aas_env_json=aas_env_json,
                            aasx_bytes=None,
                            source_url=url,
                            selected_submodel_semantic_id=reference_to_str(
                                parsed.submodel.semantic_id
                            ),
                            selection_strategy="fallback_filename_unique",
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        "template_candidate_parse_failed",
                        template_key=template_key,
                        version=version,
                        file_kind=file_kind,
                        source_url=url,
                        error=str(exc),
                    )
                continue

            candidate_aasx = response.content
            if not self._is_valid_aasx(candidate_aasx):
                continue

            try:
                aas_env_json = self._extract_aas_environment(candidate_aasx)
                if not aas_env_json.get("submodels"):
                    continue
                parsed = parser.parse_aasx(
                    candidate_aasx,
                    expected_semantic_id=descriptor.semantic_id,
                )
                matches.append(
                    TemplateCandidateResolution(
                        asset=asset,
                        kind="aasx",
                        aas_env_json=aas_env_json,
                        aasx_bytes=candidate_aasx,
                        source_url=url,
                        selected_submodel_semantic_id=reference_to_str(parsed.submodel.semantic_id),
                        selection_strategy=SELECTION_STRATEGY,
                    )
                )
                continue
            except Exception:
                pass

            try:
                parsed = parser.parse_aasx(candidate_aasx)
                parseable_fallbacks.append(
                    TemplateCandidateResolution(
                        asset=asset,
                        kind="aasx",
                        aas_env_json=self._extract_aas_environment(candidate_aasx),
                        aasx_bytes=candidate_aasx,
                        source_url=url,
                        selected_submodel_semantic_id=reference_to_str(parsed.submodel.semantic_id),
                        selection_strategy="fallback_filename_unique",
                    )
                )
            except Exception as exc:
                logger.warning(
                    "template_candidate_parse_failed",
                    template_key=template_key,
                    version=version,
                    file_kind=file_kind,
                    source_url=url,
                    error=str(exc),
                )

        selected_match = self._select_ranked_candidate_resolution(
            matches,
            descriptor=descriptor,
            version=version,
            file_kind=file_kind,
        )
        if selected_match is not None:
            return selected_match

        selected_fallback = self._select_ranked_candidate_resolution(
            parseable_fallbacks,
            descriptor=descriptor,
            version=version,
            file_kind=file_kind,
        )
        if selected_fallback is not None:
            return selected_fallback
        return None

    def _select_ranked_candidate_resolution(
        self,
        candidates: list[TemplateCandidateResolution],
        *,
        descriptor: TemplateDescriptor,
        version: str,
        file_kind: Literal["json", "aasx"],
    ) -> TemplateCandidateResolution | None:
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        expected_name = self._expected_template_filename(descriptor, version, file_kind).lower()
        exact_name_matches = [
            candidate
            for candidate in candidates
            if str((candidate.asset or {}).get("name", "")).strip().lower() == expected_name
        ]
        if len(exact_name_matches) == 1:
            return exact_name_matches[0]

        non_metamodel = [
            candidate
            for candidate in candidates
            if "foraasmetamodel" not in str((candidate.asset or {}).get("name", "")).strip().lower()
        ]
        if len(non_metamodel) == 1:
            return non_metamodel[0]

        names = sorted(
            str(candidate.asset.get("name", "")) for candidate in candidates if candidate.asset
        )
        raise TemplateFetchError(
            descriptor.key,
            version,
            f"Ambiguous {file_kind} candidates: multiple files match semantic ID ({names}).",
        )

    async def _resolve_direct_url_candidate(
        self,
        *,
        client: httpx.AsyncClient,
        template_key: str,
        descriptor: TemplateDescriptor,
        version: str,
        file_kind: Literal["json", "aasx"],
        url: str,
    ) -> TemplateCandidateResolution | None:
        parser = BasyxTemplateParser()
        try:
            response = await client.get(url)
            response.raise_for_status()
        except Exception as exc:
            logger.warning(
                "template_direct_fetch_failed",
                template_key=template_key,
                version=version,
                file_kind=file_kind,
                source_url=url,
                error=str(exc),
            )
            return None

        if file_kind == "json":
            try:
                payload = response.json()
                aas_env_json = self._normalize_template_json(payload, template_key)
                parsed = parser.parse_json(
                    json.dumps(aas_env_json).encode("utf-8"),
                    expected_semantic_id=descriptor.semantic_id,
                )
            except Exception:
                return None
            return TemplateCandidateResolution(
                asset=None,
                kind="json",
                aas_env_json=aas_env_json,
                aasx_bytes=None,
                source_url=url,
                selected_submodel_semantic_id=reference_to_str(parsed.submodel.semantic_id),
                selection_strategy="fallback_url",
            )

        candidate_aasx = response.content
        if not self._is_valid_aasx(candidate_aasx):
            return None
        try:
            parsed = parser.parse_aasx(candidate_aasx, expected_semantic_id=descriptor.semantic_id)
        except Exception:
            return None
        return TemplateCandidateResolution(
            asset=None,
            kind="aasx",
            aas_env_json=self._extract_aas_environment(candidate_aasx),
            aasx_bytes=candidate_aasx,
            source_url=url,
            selected_submodel_semantic_id=reference_to_str(parsed.submodel.semantic_id),
            selection_strategy="fallback_url",
        )

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

    def _is_valid_aasx(self, data: bytes) -> bool:
        """Check if data is a valid AASX (ZIP) file by verifying magic bytes."""
        if len(data) < 4:
            return False
        # ZIP files start with PK (0x50 0x4B)
        return data[:2] == b"PK"

    def _extract_aas_environment(self, aasx_bytes: bytes) -> dict[str, Any]:
        """
        Extract and normalize AAS Environment from an AASX package.
        """
        basyx_env = self._extract_from_basyx(aasx_bytes)
        if basyx_env is not None and basyx_env.get("submodels"):
            return self._normalize_aas_environment(basyx_env)

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

    def _extract_from_basyx(self, aasx_bytes: bytes) -> dict[str, Any] | None:
        store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
        try:
            with basyx_aasx.AASXReader(io.BytesIO(aasx_bytes)) as reader:
                files = basyx_aasx.DictSupplementaryFileContainer()  # type: ignore[no-untyped-call]
                reader.read_into(store, files)
        except (ValueError, KeyError, AttributeError, TypeError, zipfile.BadZipFile) as exc:
            logger.warning(
                "template_aasx_basyx_parse_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return None

        submodel_count = sum(1 for obj in store if isinstance(obj, model.Submodel))
        if submodel_count == 0:
            logger.warning("template_aasx_basyx_no_submodels", store_size=len(list(store)))
            return None

        env_json = basyx_json.object_store_to_json(store)  # type: ignore[attr-defined]

        # Handle both string and dict return types from object_store_to_json
        if isinstance(env_json, str):
            try:
                result = cast(dict[str, Any], json.loads(env_json))
            except json.JSONDecodeError:
                logger.warning("template_aasx_basyx_parse_invalid_json")
                return None
        elif isinstance(env_json, dict):
            result = cast(dict[str, Any], env_json)
        else:
            logger.warning(
                "template_aasx_basyx_parse_invalid_type",
                actual_type=type(env_json).__name__,
            )
            return None

        logger.debug(
            "template_aasx_basyx_parse_success",
            submodel_count=submodel_count,
        )
        return result

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

    def generate_ui_schema(
        self,
        template: Template,
        template_lookup: Mapping[str, Template] | None = None,
    ) -> dict[str, Any]:
        """
        Generate a UI schema from the canonical template definition AST.
        """
        definition = self._generate_template_definition(template, template_lookup=template_lookup)
        return DefinitionToSchemaConverter().convert(definition)

    def generate_template_contract(
        self,
        template: Template,
        template_lookup: Mapping[str, Template] | None = None,
    ) -> dict[str, Any]:
        definition = self._generate_template_definition(template, template_lookup=template_lookup)
        schema = DefinitionToSchemaConverter().convert(definition)
        dropin_resolution_report = self._collect_dropin_resolution_report(definition)
        unsupported_nodes = self._collect_unsupported_nodes(definition, schema)
        doc_hints = self._build_doc_hints(definition=definition, template=template)
        return {
            "template_key": template.template_key,
            "idta_version": template.idta_version,
            "semantic_id": template.semantic_id,
            "definition": definition,
            "schema": schema,
            "source_metadata": self._source_metadata(template),
            "dropin_resolution_report": dropin_resolution_report,
            "unsupported_nodes": unsupported_nodes,
            "doc_hints": doc_hints,
        }

    def _source_metadata(self, template: Template) -> dict[str, Any]:
        return {
            "resolved_version": template.resolved_version or template.idta_version,
            "source_repo_ref": template.source_repo_ref or self._settings.idta_templates_repo_ref,
            "source_file_path": template.source_file_path,
            "source_file_sha": template.source_file_sha,
            "source_kind": template.source_kind,
            "selection_strategy": template.selection_strategy,
            "source_url": template.source_url,
        }

    def _build_doc_hints(self, *, definition: dict[str, Any], template: Template) -> dict[str, Any]:
        qualifier_hints = self._collect_qualifier_doc_hints(definition)
        sidecar_hints = self._extract_sidecar_doc_hints(template)
        merged_semantic = dict(qualifier_hints["by_semantic_id"])
        merged_paths = dict(qualifier_hints["by_id_short_path"])

        for key, hint in sidecar_hints["by_semantic_id"].items():
            existing = merged_semantic.get(key, {})
            merged_semantic[key] = {
                **existing,
                **hint,
                "source": "sidecar",
            }
        for key, hint in sidecar_hints["by_id_short_path"].items():
            existing = merged_paths.get(key, {})
            merged_paths[key] = {
                **existing,
                **hint,
                "source": "sidecar",
            }

        entries: list[dict[str, Any]] = []
        for key, hint in sorted(merged_semantic.items(), key=lambda item: item[0]):
            entry = {"match": "semanticId", "match_key": key, **hint}
            entries.append(entry)
        for key, hint in sorted(merged_paths.items(), key=lambda item: item[0]):
            entry = {"match": "idShortPath", "match_key": key, **hint}
            entries.append(entry)

        return {
            "by_semantic_id": merged_semantic,
            "by_id_short_path": merged_paths,
            "entries": entries,
        }

    def _collect_qualifier_doc_hints(self, definition: dict[str, Any]) -> dict[str, dict[str, Any]]:
        submodel = definition.get("submodel")
        if not isinstance(submodel, dict):
            return {"by_semantic_id": {}, "by_id_short_path": {}}
        root_id_short = str(submodel.get("idShort") or "").strip()
        roots = submodel.get("elements")
        if not isinstance(roots, list):
            return {"by_semantic_id": {}, "by_id_short_path": {}}

        by_semantic: dict[str, dict[str, Any]] = {}
        by_path: dict[str, dict[str, Any]] = {}

        def relative_path(raw_path: str | None) -> str | None:
            if not raw_path:
                return None
            path = raw_path.strip().strip("/")
            if not path:
                return None
            if root_id_short and path.startswith(f"{root_id_short}/"):
                path = path[len(root_id_short) + 1 :]
            elif path == root_id_short:
                path = ""
            return path or None

        def visit(node: dict[str, Any]) -> None:
            smt = node.get("smt")
            if not isinstance(smt, dict):
                smt = {}
            semantic_id = str(node.get("semanticId") or "").strip()
            semantic_key = semantic_id.rstrip("/").lower() if semantic_id else ""
            path_key = relative_path(str(node.get("path") or "").strip())
            hint = {
                "semanticId": semantic_id or None,
                "idShortPath": path_key,
                "formTitle": smt.get("form_title"),
                "formInfo": smt.get("form_info"),
                "formUrl": smt.get("form_url"),
                "source": "qualifier",
            }
            if semantic_key and any(
                hint.get(name) for name in ("formTitle", "formInfo", "formUrl")
            ):
                by_semantic[semantic_key] = hint
            if path_key and any(hint.get(name) for name in ("formTitle", "formInfo", "formUrl")):
                by_path[path_key] = hint

            for key in ("children", "statements", "annotations"):
                children = node.get(key)
                if isinstance(children, list):
                    for child in children:
                        if isinstance(child, dict):
                            visit(child)
            list_item = node.get("items")
            if isinstance(list_item, dict):
                visit(list_item)

        for root in roots:
            if isinstance(root, dict):
                visit(root)

        return {"by_semantic_id": by_semantic, "by_id_short_path": by_path}

    def _extract_sidecar_doc_hints(self, template: Template) -> dict[str, dict[str, Any]]:
        empty = {"by_semantic_id": {}, "by_id_short_path": {}}
        if not template.template_aasx:
            return empty
        try:
            with zipfile.ZipFile(io.BytesIO(template.template_aasx), "r") as zf:
                candidate = next(
                    (
                        name
                        for name in sorted(zf.namelist())
                        if name.replace("\\", "/") == "aasx/files/ui-hints.json"
                        or name.replace("\\", "/").endswith("/ui-hints.json")
                    ),
                    None,
                )
                if candidate is None:
                    return empty
                raw = zf.read(candidate)
        except Exception:
            return empty

        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            return empty

        mappings = payload.get("mappings")
        if not isinstance(mappings, dict):
            return empty

        by_semantic: dict[str, dict[str, Any]] = {}
        by_path: dict[str, dict[str, Any]] = {}
        for _, mapping in sorted(mappings.items(), key=lambda item: str(item[0])):
            if not isinstance(mapping, dict):
                continue
            semantic_id = str(mapping.get("semanticId") or "").strip()
            semantic_key = semantic_id.rstrip("/").lower() if semantic_id else ""
            id_short_path = str(mapping.get("idShortPath") or "").strip().strip("/")
            entry = {
                "semanticId": semantic_id or None,
                "idShortPath": id_short_path or None,
                "helpText": mapping.get("helpText"),
                "formUrl": mapping.get("formUrl"),
                "pdfRef": mapping.get("pdfRef"),
                "page": mapping.get("page"),
            }
            if semantic_key:
                by_semantic[semantic_key] = entry
            if id_short_path:
                by_path[id_short_path] = entry
        return {"by_semantic_id": by_semantic, "by_id_short_path": by_path}

    def _collect_dropin_resolution_report(self, definition: dict[str, Any]) -> list[dict[str, Any]]:
        report: list[dict[str, Any]] = []
        for node in self._iter_definition_nodes(definition):
            resolution = node.get("x_resolution")
            if isinstance(resolution, dict) and resolution:
                payload = dict(resolution)
                payload.setdefault("path", node.get("path"))
                payload.setdefault("idShort", node.get("idShort"))
                payload.setdefault("modelType", node.get("modelType"))
                report.append(payload)
        report.sort(
            key=lambda item: (
                str(item.get("path") or ""),
                str(item.get("binding_id") or ""),
                str(item.get("status") or ""),
            )
        )
        return report

    def _collect_unsupported_nodes(
        self,
        definition: dict[str, Any],
        schema: dict[str, Any],
    ) -> list[dict[str, Any]]:
        unsupported_model_types = {"Blob", "Operation", "Capability", "BasicEventElement"}
        root_id_short = str((definition.get("submodel") or {}).get("idShort") or "").strip() or None
        unsupported: list[dict[str, Any]] = []
        seen: set[tuple[str | None, str | None, str]] = set()

        for node in self._iter_definition_nodes(definition):
            reasons: list[str] = []
            model_type = str(node.get("modelType") or "")
            path = str(node.get("path") or "") or None
            if model_type in unsupported_model_types:
                reasons.append(f"unsupported_model_type:{model_type}")

            resolution = node.get("x_resolution")
            if isinstance(resolution, dict):
                status = str(resolution.get("status") or "").strip().lower()
                if status and status not in {"resolved", "skipped"}:
                    reasons.append(
                        f"dropin_{str(resolution.get('reason') or status).strip().lower()}"
                    )

            schema_node = self._schema_node_for_definition_path(
                schema=schema,
                definition_path=path,
                root_id_short=root_id_short,
            )
            if isinstance(schema_node, dict) and schema_node.get("x-unresolved-definition"):
                unresolved_reason = str(schema_node.get("x-unresolved-reason") or "unresolved")
                reasons.append(f"schema_{unresolved_reason}")

            if not reasons:
                continue

            deduped_reasons = sorted({reason for reason in reasons if reason})
            key = (path, str(node.get("idShort") or ""), "|".join(deduped_reasons))
            if key in seen:
                continue
            seen.add(key)
            unsupported.append(
                {
                    "path": path,
                    "idShort": node.get("idShort"),
                    "modelType": node.get("modelType"),
                    "semanticId": node.get("semanticId"),
                    "reasons": deduped_reasons,
                }
            )

        unsupported.sort(
            key=lambda item: (
                str(item.get("path") or ""),
                str(item.get("idShort") or ""),
                str(item.get("modelType") or ""),
            )
        )
        return unsupported

    def _iter_definition_nodes(self, definition: dict[str, Any]) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []

        def walk(node: dict[str, Any]) -> None:
            nodes.append(node)
            for key in (
                "children",
                "statements",
                "annotations",
                "input_variable",
                "output_variable",
                "in_output_variable",
            ):
                value = node.get(key)
                if isinstance(value, list):
                    for child in value:
                        if isinstance(child, dict):
                            walk(child)
            items = node.get("items")
            if isinstance(items, dict):
                walk(items)

        elements = (definition.get("submodel") or {}).get("elements") or []
        if isinstance(elements, list):
            for element in elements:
                if isinstance(element, dict):
                    walk(element)
        return nodes

    def _schema_node_for_definition_path(
        self,
        *,
        schema: dict[str, Any],
        definition_path: str | None,
        root_id_short: str | None,
    ) -> dict[str, Any] | None:
        if not definition_path:
            return None
        parts = [part for part in definition_path.split("/") if part]
        if root_id_short and parts and parts[0] == root_id_short:
            parts = parts[1:]

        current: dict[str, Any] | None = schema
        for part in parts:
            if current is None:
                return None
            is_list_part = part.endswith("[]")
            key = part[:-2] if is_list_part else part

            current_type = str(current.get("type") or "")
            if key:
                if current_type == "object":
                    properties = current.get("properties")
                    if not isinstance(properties, dict):
                        return None
                    child = properties.get(key)
                    if not isinstance(child, dict):
                        return None
                    current = child
                elif current_type == "array":
                    child = current.get("items")
                    if not isinstance(child, dict):
                        return None
                    current = child
                    if key:
                        properties = current.get("properties")
                        if not isinstance(properties, dict):
                            return None
                        nested = properties.get(key)
                        if not isinstance(nested, dict):
                            return None
                        current = nested
                else:
                    return None

            if is_list_part:
                items = current.get("items")
                if not isinstance(items, dict):
                    return None
                current = items

        return current
