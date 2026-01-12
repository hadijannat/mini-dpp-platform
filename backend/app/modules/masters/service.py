"""Service layer for DPP master templates and released versions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import (
    DPPMaster,
    DPPMasterAlias,
    DPPMasterVersion,
    MasterVersionStatus,
)
from app.modules.dpps.basyx_builder import BasyxDppBuilder
from app.modules.masters.placeholders import (
    extract_placeholder_paths,
    json_pointer_to_path,
    resolve_json_pointer,
    set_json_pointer,
)
from app.modules.templates.service import TemplateRegistryService

logger = get_logger(__name__)

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


@dataclass(frozen=True)
class VariableSpec:
    name: str
    label: str
    description: str | None
    required: bool
    default_value: Any
    allow_default: bool
    expected_type: str
    constraints: dict[str, Any] | None
    paths: list[dict[str, str]]


class DPPMasterService:
    """Service for managing DPP master templates and released versions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._template_service = TemplateRegistryService(session)
        self._builder = BasyxDppBuilder(self._template_service)

    async def list_masters(
        self,
        tenant_id: UUID,
        product_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DPPMaster]:
        query = (
            select(DPPMaster)
            .where(DPPMaster.tenant_id == tenant_id)
            .order_by(DPPMaster.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if product_id:
            query = query.where(DPPMaster.product_id == product_id)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_master(self, master_id: UUID, tenant_id: UUID) -> DPPMaster | None:
        result = await self._session.execute(
            select(DPPMaster).where(
                DPPMaster.id == master_id,
                DPPMaster.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_master_by_product(self, tenant_id: UUID, product_id: str) -> DPPMaster | None:
        result = await self._session.execute(
            select(DPPMaster).where(
                DPPMaster.tenant_id == tenant_id,
                DPPMaster.product_id == product_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_versions(self, master_id: UUID) -> list[DPPMasterVersion]:
        result = await self._session.execute(
            select(DPPMasterVersion)
            .where(DPPMasterVersion.master_id == master_id)
            .order_by(DPPMasterVersion.released_at.desc())
        )
        return list(result.scalars().all())

    async def create_master(
        self,
        tenant_id: UUID,
        created_by: str,
        product_id: str,
        name: str,
        description: str | None,
        selected_templates: list[str],
        asset_ids: dict[str, Any] | None,
        initial_data: dict[str, Any] | None,
        template_json: dict[str, Any] | None,
        variables: list[dict[str, Any]] | None,
    ) -> DPPMaster:
        if template_json is None:
            if not asset_ids:
                raise ValueError("asset_ids are required when template_json is not provided")
            if not selected_templates:
                raise ValueError(
                    "selected_templates are required when template_json is not provided"
                )
            template_json = await self._builder.build_environment(
                asset_ids=asset_ids,
                selected_templates=selected_templates,
                initial_data=initial_data or {},
            )

        if variables is None:
            variables = self._default_variables_from_template(template_json)

        master = DPPMaster(
            tenant_id=tenant_id,
            product_id=product_id,
            name=name,
            description=description,
            selected_templates=selected_templates,
            draft_template_json=template_json,
            draft_variables=variables,
            created_by_subject=created_by,
            updated_by_subject=created_by,
        )
        self._session.add(master)
        await self._session.flush()
        logger.info("dpp_master_created", master_id=str(master.id), product_id=product_id)
        return master

    async def update_master(
        self,
        master: DPPMaster,
        updated_by: str,
        name: str | None = None,
        description: str | None = None,
        selected_templates: list[str] | None = None,
        asset_ids: dict[str, Any] | None = None,
        initial_data: dict[str, Any] | None = None,
        template_json: dict[str, Any] | None = None,
        variables: list[dict[str, Any]] | None = None,
    ) -> DPPMaster:
        if name is not None:
            master.name = name
        if description is not None:
            master.description = description

        if template_json is not None:
            master.draft_template_json = template_json
        elif selected_templates is not None:
            if not asset_ids:
                raise ValueError("asset_ids are required when rebuilding from templates")
            master.draft_template_json = await self._builder.build_environment(
                asset_ids=asset_ids,
                selected_templates=selected_templates,
                initial_data=initial_data or {},
            )
            master.selected_templates = selected_templates

        if variables is not None:
            master.draft_variables = variables

        master.updated_by_subject = updated_by
        await self._session.flush()
        logger.info("dpp_master_updated", master_id=str(master.id))
        return master

    async def release_version(
        self,
        master: DPPMaster,
        released_by: str,
        version: str,
        aliases: list[str],
        update_latest: bool,
    ) -> DPPMasterVersion:
        if not SEMVER_PATTERN.match(version):
            raise ValueError("version must follow semantic versioning (e.g., 1.0.0)")

        result = await self._session.execute(
            select(DPPMasterVersion).where(
                DPPMasterVersion.master_id == master.id,
                DPPMasterVersion.version == version,
            )
        )
        if result.scalar_one_or_none():
            raise ValueError(f"Version {version} already exists for master {master.id}")

        normalized_aliases = self._normalize_aliases(aliases)
        if update_latest and "latest" not in normalized_aliases:
            normalized_aliases.append("latest")
        elif "latest" in normalized_aliases:
            update_latest = True

        variables = self._build_version_variables(
            master.draft_variables, master.draft_template_json
        )

        released = DPPMasterVersion(
            tenant_id=master.tenant_id,
            master_id=master.id,
            version=version,
            status=MasterVersionStatus.RELEASED,
            aliases=normalized_aliases,
            template_json=json.loads(json.dumps(master.draft_template_json)),
            variables=variables,
            released_by_subject=released_by,
        )
        self._session.add(released)
        await self._session.flush()

        await self._sync_aliases(master, released, normalized_aliases, update_latest)

        logger.info(
            "dpp_master_version_released",
            master_id=str(master.id),
            version=version,
        )
        return released

    async def update_aliases(
        self,
        master: DPPMaster,
        version: DPPMasterVersion,
        aliases: list[str],
    ) -> DPPMasterVersion:
        normalized = self._normalize_aliases(aliases)
        version.aliases = normalized
        await self._session.flush()

        await self._sync_aliases(master, version, normalized, "latest" in normalized)

        logger.info(
            "dpp_master_aliases_updated",
            master_id=str(master.id),
            version=version.version,
        )
        return version

    async def get_version_by_selector(
        self,
        master_id: UUID,
        version_or_alias: str,
    ) -> DPPMasterVersion | None:
        selector = version_or_alias.strip()
        result = await self._session.execute(
            select(DPPMasterVersion).where(
                DPPMasterVersion.master_id == master_id,
                DPPMasterVersion.version == selector,
            )
        )
        found = result.scalar_one_or_none()
        if found:
            return found

        result = await self._session.execute(
            select(DPPMasterVersion)
            .join(DPPMasterAlias, DPPMasterAlias.version_id == DPPMasterVersion.id)
            .where(
                DPPMasterVersion.master_id == master_id,
                DPPMasterAlias.alias == selector.lower(),
            )
        )
        return result.scalar_one_or_none()

    async def get_version_for_product(
        self,
        tenant_id: UUID,
        product_id: str,
        version_or_alias: str,
    ) -> tuple[DPPMaster, DPPMasterVersion] | None:
        master = await self.get_master_by_product(tenant_id, product_id)
        if not master:
            return None
        version = await self.get_version_by_selector(master.id, version_or_alias)
        if not version:
            return None
        return master, version

    def build_template_package(
        self, master: DPPMaster, version: DPPMasterVersion
    ) -> dict[str, Any]:
        return {
            "master_id": str(master.id),
            "product_id": master.product_id,
            "name": master.name,
            "version": version.version,
            "aliases": version.aliases,
            "template_string": json.dumps(
                version.template_json,
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
            ),
            "variables": version.variables,
        }

    def validate_instance_payload(
        self, payload: dict[str, Any], version: DPPMasterVersion
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        errors: list[dict[str, Any]] = []
        unresolved_map = extract_placeholder_paths(payload)
        for name, pointers in unresolved_map.items():
            errors.append(
                {
                    "code": "unresolved_placeholder",
                    "name": name,
                    "paths": [
                        {
                            "jsonPointer": pointer,
                            "jsonPath": json_pointer_to_path(pointer),
                        }
                        for pointer in pointers
                    ],
                }
            )

        variables = self._parse_variables(version.variables)
        for variable in variables:
            for path_entry in variable.paths:
                pointer = path_entry.get("jsonPointer", "")
                if not pointer:
                    continue
                value = resolve_json_pointer(payload, pointer)

                if _is_missing(value):
                    if variable.allow_default and variable.default_value is not None:
                        set_json_pointer(payload, pointer, variable.default_value)
                        value = resolve_json_pointer(payload, pointer)
                    elif variable.required:
                        errors.append(
                            {
                                "code": "missing_required",
                                "name": variable.name,
                                "path": pointer,
                            }
                        )
                        continue
                    else:
                        continue

                coerced, error = _coerce_value(value, variable.expected_type)
                if error:
                    errors.append(
                        {
                            "code": "type_mismatch",
                            "name": variable.name,
                            "path": pointer,
                            "expected_type": variable.expected_type,
                            "message": error,
                        }
                    )
                    continue
                if coerced is not value:
                    set_json_pointer(payload, pointer, coerced)

        return payload, errors

    async def _sync_aliases(
        self,
        master: DPPMaster,
        version: DPPMasterVersion,
        aliases: list[str],
        move_latest: bool,
    ) -> None:
        normalized = list(aliases)
        if move_latest and "latest" not in normalized:
            normalized.append("latest")

        result = await self._session.execute(
            select(DPPMasterAlias).where(DPPMasterAlias.master_id == master.id)
        )
        existing = list(result.scalars().all())
        by_alias = {row.alias: row for row in existing}

        # Assign aliases to this version, moving from other versions when needed.
        for alias in normalized:
            row = by_alias.get(alias)
            if row:
                row.version_id = version.id
            else:
                self._session.add(
                    DPPMasterAlias(
                        tenant_id=master.tenant_id,
                        master_id=master.id,
                        version_id=version.id,
                        alias=alias,
                    )
                )

        # Remove aliases from this version that are no longer desired.
        for row in existing:
            if row.version_id == version.id and row.alias not in normalized:
                self._session.delete(row)

        await self._refresh_aliases(master.id)

    async def _refresh_aliases(self, master_id: UUID) -> None:
        result = await self._session.execute(
            select(DPPMasterAlias).where(DPPMasterAlias.master_id == master_id)
        )
        alias_rows = list(result.scalars().all())
        alias_map: dict[UUID, list[str]] = {}
        for row in alias_rows:
            alias_map.setdefault(row.version_id, []).append(row.alias)

        result = await self._session.execute(
            select(DPPMasterVersion).where(DPPMasterVersion.master_id == master_id)
        )
        versions = list(result.scalars().all())
        for version in versions:
            version.aliases = sorted(alias_map.get(version.id, []))
        await self._session.flush()

    def _normalize_aliases(self, aliases: list[str]) -> list[str]:
        cleaned: list[str] = []
        for alias in aliases:
            normalized = alias.strip().lower()
            if not normalized:
                continue
            if normalized not in cleaned:
                cleaned.append(normalized)
        return cleaned

    def _default_variables_from_template(
        self, template_json: dict[str, Any]
    ) -> list[dict[str, Any]]:
        placeholders = extract_placeholder_paths(template_json)
        defaults: list[dict[str, Any]] = []
        for name in sorted(placeholders.keys()):
            defaults.append(
                {
                    "name": name,
                    "label": _humanize_name(name),
                    "description": None,
                    "required": True,
                    "default_value": None,
                    "allow_default": True,
                    "expected_type": "string",
                    "constraints": None,
                }
            )
        return defaults

    def _build_version_variables(
        self, draft_variables: list[dict[str, Any]], template_json: dict[str, Any]
    ) -> list[dict[str, Any]]:
        placeholder_map = extract_placeholder_paths(template_json)
        normalized: dict[str, dict[str, Any]] = {}

        for entry in draft_variables:
            spec = self._normalize_variable(entry)
            if spec["name"]:
                normalized[spec["name"]] = spec

        for name in placeholder_map:
            if name not in normalized:
                normalized[name] = {
                    "name": name,
                    "label": _humanize_name(name),
                    "description": None,
                    "required": True,
                    "default_value": None,
                    "allow_default": True,
                    "expected_type": "string",
                    "constraints": None,
                }

        for name, spec in normalized.items():
            pointers = placeholder_map.get(name, [])
            spec["paths"] = [
                {
                    "jsonPointer": pointer,
                    "jsonPath": json_pointer_to_path(pointer),
                }
                for pointer in pointers
            ]

        return list(normalized.values())

    def _normalize_variable(self, raw: dict[str, Any]) -> dict[str, Any]:
        name = str(raw.get("name", "")).strip()
        label = raw.get("label") or _humanize_name(name)
        description = raw.get("description")
        required = bool(raw.get("required", True))
        allow_default = bool(raw.get("allow_default", True))
        expected_type = str(raw.get("expected_type", "string")).strip().lower() or "string"
        constraints = raw.get("constraints")
        return {
            "name": name,
            "label": label,
            "description": description,
            "required": required,
            "default_value": raw.get("default_value"),
            "allow_default": allow_default,
            "expected_type": expected_type,
            "constraints": constraints,
        }

    def _parse_variables(self, raw_variables: list[dict[str, Any]]) -> list[VariableSpec]:
        specs: list[VariableSpec] = []
        for raw in raw_variables:
            name = str(raw.get("name", "")).strip()
            if not name:
                continue
            label = raw.get("label") or _humanize_name(name)
            paths = raw.get("paths")
            if not isinstance(paths, list):
                paths = []
            parsed_paths = [
                {
                    "jsonPointer": str(entry.get("jsonPointer", "")),
                    "jsonPath": str(entry.get("jsonPath", "")),
                }
                for entry in paths
                if isinstance(entry, dict)
            ]
            specs.append(
                VariableSpec(
                    name=name,
                    label=str(label),
                    description=raw.get("description"),
                    required=bool(raw.get("required", True)),
                    default_value=raw.get("default_value"),
                    allow_default=bool(raw.get("allow_default", True)),
                    expected_type=str(raw.get("expected_type", "string")).lower(),
                    constraints=raw.get("constraints"),
                    paths=parsed_paths,
                )
            )
        return specs


def _humanize_name(name: str) -> str:
    if not name:
        return ""
    if "_" in name:
        parts = [part for part in name.split("_") if part]
        return " ".join(part.capitalize() for part in parts)
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return spaced[:1].upper() + spaced[1:]


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return isinstance(value, (list, dict)) and not value


def _coerce_value(value: Any, expected_type: str) -> tuple[Any, str | None]:
    expected_type = expected_type.lower()
    if expected_type == "string":
        if isinstance(value, (dict, list)):
            return value, "Expected string but received complex value"
        if value is None:
            return value, None
        return str(value), None

    if expected_type in {"number", "float"}:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value), None
        if isinstance(value, str):
            try:
                return float(value), None
            except ValueError:
                return value, "Expected number"
        return value, "Expected number"

    if expected_type == "integer":
        if isinstance(value, int) and not isinstance(value, bool):
            return value, None
        if isinstance(value, float) and value.is_integer():
            return int(value), None
        if isinstance(value, str):
            if value.strip() == "":
                return value, "Expected integer"
            try:
                return int(value), None
            except ValueError:
                return value, "Expected integer"
        return value, "Expected integer"

    if expected_type == "boolean":
        if isinstance(value, bool):
            return value, None
        if isinstance(value, (int, float)):
            if value in (0, 1):
                return bool(value), None
            return value, "Expected boolean"
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "false"}:
                return lowered == "true", None
            if lowered in {"0", "1"}:
                return lowered == "1", None
        return value, "Expected boolean"

    if expected_type == "object":
        if isinstance(value, dict):
            return value, None
        return value, "Expected object"

    if expected_type == "array":
        if isinstance(value, list):
            return value, None
        return value, "Expected array"

    return value, None
