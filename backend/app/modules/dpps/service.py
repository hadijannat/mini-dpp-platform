"""
DPP (Digital Product Passport) Core Service.
Handles DPP lifecycle, revision management, and data hydration.
"""

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import DPP, DPPRevision, DPPStatus, RevisionState, Template, User, UserRole
from app.modules.templates.service import TemplateRegistryService

logger = get_logger(__name__)


class DPPService:
    """
    Core service for Digital Product Passport operations.

    Manages DPP creation, editing, publishing, and revision history.
    All edits create new revisions to maintain complete audit trails.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
        self._template_service = TemplateRegistryService(session)

    async def _ensure_user_exists(self, subject: str) -> User:
        """
        Ensure a user exists for the given OIDC subject.

        Auto-provisions users on first API access (just-in-time provisioning).
        """
        result = await self._session.execute(select(User).where(User.subject == subject))
        user = result.scalar_one_or_none()

        if user is None:
            # Auto-provision user with publisher role
            user = User(
                subject=subject,
                role=UserRole.PUBLISHER,
                attrs={},
            )
            self._session.add(user)
            await self._session.flush()
            logger.info("user_auto_provisioned", subject=subject)

        return user

    async def create_dpp(
        self,
        owner_subject: str,
        asset_ids: dict[str, Any],
        selected_templates: list[str],
        initial_data: dict[str, Any] | None = None,
    ) -> DPP:
        """
        Create a new DPP with initial draft revision.

        Args:
            owner_subject: OIDC subject of the creating user
            asset_ids: AAS specificAssetIds (manufacturerPartId, serialNumber, etc.)
            selected_templates: List of template keys to include
            initial_data: Optional initial values for submodel elements

        Returns:
            The created DPP with its first revision
        """
        # Ensure user exists (auto-provision if needed)
        await self._ensure_user_exists(owner_subject)

        # Build initial AAS Environment from selected templates
        aas_env = await self._build_initial_environment(
            asset_ids,
            selected_templates,
            initial_data or {},
        )

        # Calculate content digest
        digest = self._calculate_digest(aas_env)

        # Create DPP record
        dpp = DPP(
            status=DPPStatus.DRAFT,
            owner_subject=owner_subject,
            asset_ids=asset_ids,
        )
        self._session.add(dpp)
        await self._session.flush()

        # Generate QR payload URL
        dpp.qr_payload = f"{self._settings.api_v1_prefix.rstrip('/')}/dpps/{dpp.id}"

        # Create initial revision
        revision = DPPRevision(
            dpp_id=dpp.id,
            revision_no=1,
            state=RevisionState.DRAFT,
            aas_env_json=aas_env,
            digest_sha256=digest,
            created_by_subject=owner_subject,
        )
        self._session.add(revision)
        await self._session.flush()

        logger.info(
            "dpp_created",
            dpp_id=str(dpp.id),
            owner=owner_subject,
            templates=selected_templates,
        )

        return dpp

    async def get_dpp(
        self,
        dpp_id: UUID,
        include_revisions: bool = False,
    ) -> DPP | None:
        """
        Get a DPP by ID with optional revision history.
        """
        query = select(DPP).where(DPP.id == dpp_id)

        if include_revisions:
            query = query.options(selectinload(DPP.revisions))

        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_dpps_for_owner(
        self,
        owner_subject: str,
        status: DPPStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DPP]:
        """
        Get all DPPs owned by a specific user.
        """
        query = (
            select(DPP)
            .where(DPP.owner_subject == owner_subject)
            .order_by(DPP.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )

        if status:
            query = query.where(DPP.status == status)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_published_dpps(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DPP]:
        """
        Get all published DPPs (viewer access).
        """
        query = (
            select(DPP)
            .where(DPP.status == DPPStatus.PUBLISHED)
            .order_by(DPP.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_latest_revision(self, dpp_id: UUID) -> DPPRevision | None:
        """
        Get the latest revision of a DPP (draft or published).
        """
        result = await self._session.execute(
            select(DPPRevision)
            .where(DPPRevision.dpp_id == dpp_id)
            .order_by(DPPRevision.revision_no.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_published_revision(self, dpp_id: UUID) -> DPPRevision | None:
        """
        Get the current published revision of a DPP.
        """
        dpp = await self.get_dpp(dpp_id)
        if not dpp or not dpp.current_published_revision_id:
            return None

        result = await self._session.execute(
            select(DPPRevision).where(DPPRevision.id == dpp.current_published_revision_id)
        )
        return result.scalar_one_or_none()

    async def update_submodel(
        self,
        dpp_id: UUID,
        template_key: str,
        submodel_data: dict[str, Any],
        updated_by_subject: str,
        rebuild_from_template: bool = False,
    ) -> DPPRevision:
        """
        Update a specific submodel within a DPP.

        Creates a new draft revision with the updated submodel data.
        The previous revision remains unchanged for audit purposes.

        Args:
            dpp_id: ID of the DPP to update
            template_key: Key of the submodel template being updated
            submodel_data: New submodel element values
            updated_by_subject: OIDC subject of the updating user

        Returns:
            The newly created revision
        """
        # Get current revision
        current_revision = await self.get_latest_revision(dpp_id)
        if not current_revision:
            raise ValueError(f"DPP {dpp_id} not found")

        # Clone current AAS environment
        aas_env = json.loads(json.dumps(current_revision.aas_env_json))

        # Find and update the target submodel
        submodels = aas_env.get("submodels", [])
        template = await self._template_service.get_template(template_key)
        if not template:
            try:
                template = await self._template_service.refresh_template(template_key)
            except Exception as exc:
                logger.warning(
                    "template_missing_and_refresh_failed",
                    template_key=template_key,
                    error=str(exc),
                )
                template = None

        if not template:
            raise ValueError(f"Template {template_key} not found")

        # Find submodel by semantic ID
        target_semantic_id = template.semantic_id
        updated = False

        def matches_semantic_id(candidate: dict[str, Any]) -> bool:
            sm_semantic_id = candidate.get("semanticId", {}).get("keys", [{}])[0].get("value", "")
            return target_semantic_id in sm_semantic_id

        existing_index = next(
            (i for i, submodel in enumerate(submodels) if matches_semantic_id(submodel)),
            None,
        )

        template_submodels = template.template_json.get("submodels", [])
        candidates = [sm for sm in template_submodels if matches_semantic_id(sm)]
        if candidates:
            base_submodel = candidates[0]
        elif template_submodels:
            base_submodel = template_submodels[0]
        else:
            base_submodel = None

        if rebuild_from_template and base_submodel:
            dpp = await self.get_dpp(dpp_id)
            asset_ids = dpp.asset_ids if dpp else {}
            existing_id = None
            if existing_index is not None:
                existing_id = submodels[existing_index].get("id")
            submodel_id = existing_id or (
                f"urn:dpp:sm:{template_key}:{asset_ids.get('manufacturerPartId', 'unknown')}"
            )

            new_submodel = json.loads(json.dumps(base_submodel))
            new_submodel["id"] = submodel_id
            new_submodel = await self._hydrate_submodel(new_submodel, submodel_data)

            if existing_index is not None:
                submodels[existing_index] = new_submodel
            else:
                submodels.append(new_submodel)
                shells = aas_env.get("assetAdministrationShells", [])
                if shells:
                    refs = shells[0].setdefault("submodelRefs", [])
                    refs.append(
                        {
                            "type": "ModelReference",
                            "keys": [{"type": "Submodel", "value": submodel_id}],
                        }
                    )
            updated = True

        if not updated and existing_index is not None:
            submodels[existing_index] = await self._hydrate_submodel(
                submodels[existing_index],
                submodel_data,
            )
            updated = True

        if not updated:
            if not base_submodel:
                raise ValueError(f"Submodel {template_key} not found in DPP")

            dpp = await self.get_dpp(dpp_id)
            asset_ids = dpp.asset_ids if dpp else {}
            submodel_id = (
                f"urn:dpp:sm:{template_key}:{asset_ids.get('manufacturerPartId', 'unknown')}"
            )

            new_submodel = json.loads(json.dumps(base_submodel))
            new_submodel["id"] = submodel_id
            new_submodel = await self._hydrate_submodel(new_submodel, submodel_data)
            submodels.append(new_submodel)

            shells = aas_env.get("assetAdministrationShells", [])
            if shells:
                refs = shells[0].setdefault("submodelRefs", [])
                refs.append(
                    {
                        "type": "ModelReference",
                        "keys": [{"type": "Submodel", "value": submodel_id}],
                    }
                )
            updated = True

        aas_env["submodels"] = submodels

        # Calculate new digest
        digest = self._calculate_digest(aas_env)

        # Create new revision
        new_revision_no = current_revision.revision_no + 1

        revision = DPPRevision(
            dpp_id=dpp_id,
            revision_no=new_revision_no,
            state=RevisionState.DRAFT,
            aas_env_json=aas_env,
            digest_sha256=digest,
            created_by_subject=updated_by_subject,
        )
        self._session.add(revision)
        await self._session.flush()

        logger.info(
            "submodel_updated",
            dpp_id=str(dpp_id),
            template_key=template_key,
            revision_no=new_revision_no,
        )

        return revision

    async def rebuild_all_from_templates(
        self,
        updated_by_subject: str,
    ) -> dict[str, Any]:
        """
        Rebuild all DPP submodels from the latest templates.

        Creates a new draft revision per DPP when changes are applied.
        """
        templates = await self._template_service.get_all_templates()
        if not templates:
            templates = await self._template_service.refresh_all_templates()

        result = await self._session.execute(select(DPP))
        dpps = list(result.scalars().all())

        summary: dict[str, Any] = {
            "total": len(dpps),
            "updated": 0,
            "skipped": 0,
            "errors": [],
        }

        for dpp in dpps:
            try:
                updated = await self._rebuild_dpp_from_templates(
                    dpp,
                    templates,
                    updated_by_subject,
                )
                if updated:
                    summary["updated"] += 1
                else:
                    summary["skipped"] += 1
            except Exception as exc:  # pragma: no cover - defensive
                summary["errors"].append(
                    {
                        "dpp_id": dpp.id,
                        "error": str(exc),
                    }
                )
                summary["skipped"] += 1

        return summary

    async def publish_dpp(
        self,
        dpp_id: UUID,
        published_by_subject: str,
    ) -> DPP:
        """
        Publish a DPP, making its current draft visible to viewers.

        Creates a published revision from the latest draft and updates
        the DPP status and current_published_revision_id.
        """
        dpp = await self.get_dpp(dpp_id)
        if not dpp:
            raise ValueError(f"DPP {dpp_id} not found")

        # Get latest draft revision
        latest_revision = await self.get_latest_revision(dpp_id)
        if not latest_revision:
            raise ValueError(f"No revision found for DPP {dpp_id}")

        if latest_revision.state == RevisionState.PUBLISHED:
            # Already published, create new revision
            new_revision_no = latest_revision.revision_no + 1
            revision = DPPRevision(
                dpp_id=dpp_id,
                revision_no=new_revision_no,
                state=RevisionState.PUBLISHED,
                aas_env_json=latest_revision.aas_env_json,
                digest_sha256=latest_revision.digest_sha256,
                created_by_subject=published_by_subject,
            )
            self._session.add(revision)
            await self._session.flush()
        else:
            # Mark current draft as published
            latest_revision.state = RevisionState.PUBLISHED
            revision = latest_revision

        # Update DPP status and pointer
        dpp.status = DPPStatus.PUBLISHED
        dpp.current_published_revision_id = revision.id

        await self._session.flush()

        logger.info(
            "dpp_published",
            dpp_id=str(dpp_id),
            revision_no=revision.revision_no,
            published_by=published_by_subject,
        )

        return dpp

    async def _rebuild_dpp_from_templates(
        self,
        dpp: DPP,
        templates: list[Template],
        updated_by_subject: str,
    ) -> bool:
        current_revision = await self.get_latest_revision(dpp.id)
        if not current_revision:
            return False

        aas_env = json.loads(json.dumps(current_revision.aas_env_json))
        submodels = aas_env.get("submodels", [])
        if not submodels:
            return False

        rebuilt_submodels: list[dict[str, Any]] = []
        changed = False

        for submodel in submodels:
            template = self._match_template_for_submodel(submodel, templates)
            if not template:
                rebuilt_submodels.append(submodel)
                continue

            base_submodel = self._select_template_submodel(template)
            if not base_submodel:
                rebuilt_submodels.append(submodel)
                continue

            submodel_data = self._extract_submodel_data(submodel)
            new_submodel = json.loads(json.dumps(base_submodel))

            if submodel.get("id"):
                new_submodel["id"] = submodel.get("id")

            new_submodel = await self._hydrate_submodel(new_submodel, submodel_data)
            rebuilt_submodels.append(new_submodel)
            changed = True

        if not changed:
            return False

        aas_env["submodels"] = rebuilt_submodels
        digest = self._calculate_digest(aas_env)
        new_revision_no = current_revision.revision_no + 1

        revision = DPPRevision(
            dpp_id=dpp.id,
            revision_no=new_revision_no,
            state=RevisionState.DRAFT,
            aas_env_json=aas_env,
            digest_sha256=digest,
            created_by_subject=updated_by_subject,
        )
        self._session.add(revision)
        await self._session.flush()

        logger.info(
            "dpp_rebuilt_from_templates",
            dpp_id=str(dpp.id),
            revision_no=new_revision_no,
        )

        return True

    async def archive_dpp(self, dpp_id: UUID) -> DPP:
        """
        Archive a DPP, marking it as no longer active.
        """
        dpp = await self.get_dpp(dpp_id)
        if not dpp:
            raise ValueError(f"DPP {dpp_id} not found")

        dpp.status = DPPStatus.ARCHIVED
        await self._session.flush()

        logger.info("dpp_archived", dpp_id=str(dpp_id))

        return dpp

    async def _build_initial_environment(
        self,
        asset_ids: dict[str, Any],
        selected_templates: list[str],
        initial_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build initial AAS Environment from selected templates.
        """
        aas_env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [],
            "conceptDescriptions": [],
        }

        # Create Asset Administration Shell
        aas_id = f"urn:dpp:aas:{asset_ids.get('manufacturerPartId', 'unknown')}"

        aas: dict[str, Any] = {
            "id": aas_id,
            "idShort": f"DPP_{asset_ids.get('manufacturerPartId', 'Product')}",
            "assetInformation": {
                "assetKind": "Instance",
                "globalAssetId": asset_ids.get("globalAssetId", aas_id),
                "specificAssetIds": [
                    {"name": k, "value": str(v)}
                    for k, v in asset_ids.items()
                    if k != "globalAssetId"
                ],
            },
            "submodelRefs": [],
        }

        # Add submodels from selected templates
        for template_key in selected_templates:
            template = await self._template_service.get_template(template_key)
            if not template:
                try:
                    template = await self._template_service.refresh_template(template_key)
                except Exception as exc:
                    logger.warning(
                        "template_missing_and_refresh_failed",
                        template_key=template_key,
                        error=str(exc),
                    )
                    template = None
            if not template:
                logger.warning("template_not_found", template_key=template_key)
                continue

            # Clone template submodel(s)
            template_submodels = template.template_json.get("submodels", [])

            for sm_template in template_submodels:
                # Create instance from template
                submodel_id = (
                    f"urn:dpp:sm:{template_key}:{asset_ids.get('manufacturerPartId', 'unknown')}"
                )

                submodel = json.loads(json.dumps(sm_template))
                submodel["id"] = submodel_id

                # Apply initial data if provided
                if template_key in initial_data:
                    submodel = await self._hydrate_submodel(
                        submodel,
                        initial_data[template_key],
                    )

                aas_env["submodels"].append(submodel)

                # Add reference to AAS
                aas["submodelRefs"].append(
                    {
                        "type": "ModelReference",
                        "keys": [{"type": "Submodel", "value": submodel_id}],
                    }
                )

            # Include concept descriptions
            template_cds = template.template_json.get("conceptDescriptions", [])
            aas_env["conceptDescriptions"].extend(template_cds)

        aas_env["assetAdministrationShells"].append(aas)

        return aas_env

    def _match_template_for_submodel(
        self,
        submodel: dict[str, Any],
        templates: list[Template],
    ) -> Template | None:
        sm_semantic_id = (
            submodel.get("semanticId", {}).get("keys", [{}])[0].get("value", "")
        )
        for template in templates:
            if template.semantic_id and template.semantic_id in sm_semantic_id:
                return template
        return None

    def _select_template_submodel(
        self,
        template: Template,
    ) -> dict[str, Any] | None:
        template_submodels = template.template_json.get("submodels", [])
        candidates: list[dict[str, Any]] = []
        for candidate in template_submodels:
            candidate_semantic_id = (
                candidate.get("semanticId", {}).get("keys", [{}])[0].get("value", "")
            )
            if template.semantic_id in candidate_semantic_id:
                candidates.append(candidate)
        if candidates:
            return candidates[0]
        return template_submodels[0] if template_submodels else None

    async def _hydrate_submodel(
        self,
        submodel: dict[str, Any],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Hydrate a submodel with provided data values.

        Maps form data to AAS submodel element structure.
        """
        elements = submodel.get("submodelElements", [])

        hydrated_elements = self._hydrate_elements(elements, data)
        submodel["submodelElements"] = hydrated_elements

        return submodel

    def _extract_submodel_data(self, submodel: dict[str, Any]) -> dict[str, Any]:
        elements = submodel.get("submodelElements", [])
        return self._extract_elements(elements)

    def _extract_elements(self, elements: list[dict[str, Any]]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for element in elements:
            id_short = element.get("idShort")
            if not id_short:
                continue
            data[id_short] = self._extract_element_value(element)
        return data

    def _extract_element_value(self, element: dict[str, Any]) -> Any:
        element_type = element.get("modelType", {}).get("name", "Property")

        if element_type == "SubmodelElementCollection":
            return self._extract_elements(element.get("value", []))
        if element_type == "SubmodelElementList":
            items = element.get("value", [])
            if isinstance(items, list):
                return [
                    self._extract_element_value(item)
                    if isinstance(item, dict)
                    else item
                    for item in items
                ]
            return []
        if element_type == "MultiLanguageProperty":
            value = element.get("value", [])
            if isinstance(value, list):
                return {
                    entry.get("language"): entry.get("text", "")
                    for entry in value
                    if entry.get("language")
                }
            if isinstance(value, dict):
                return value
        if element_type == "Range":
            return {"min": element.get("min"), "max": element.get("max")}
        if element_type == "File":
            return {
                "contentType": element.get("contentType", ""),
                "value": element.get("value", ""),
            }
        if element_type == "Blob":
            return {
                "contentType": element.get("contentType", ""),
                "value": element.get("value", ""),
            }
        if element_type == "ReferenceElement":
            reference = element.get("value", {}) if isinstance(element.get("value"), dict) else {}
            return {
                "type": reference.get("type", "ModelReference"),
                "keys": reference.get("keys", []),
            }
        if element_type == "Entity":
            return {
                "entityType": element.get("entityType"),
                "globalAssetId": element.get("globalAssetId", ""),
                "statements": self._extract_elements(element.get("statements", [])),
            }
        if element_type == "RelationshipElement":
            return {
                "first": element.get("first"),
                "second": element.get("second"),
            }
        if element_type == "AnnotatedRelationshipElement":
            return {
                "first": element.get("first"),
                "second": element.get("second"),
                "annotations": self._extract_elements(element.get("annotations", [])),
            }

        return element.get("value")

    def _hydrate_elements(
        self,
        elements: list[dict[str, Any]],
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Recursively hydrate submodel elements with data values.
        """
        hydrated: list[dict[str, Any]] = []

        for element in elements:
            id_short = element.get("idShort", "")
            hydrated_element = json.loads(json.dumps(element))

            if id_short in data:
                hydrated_element = self._hydrate_element_value(hydrated_element, data[id_short])

            hydrated.append(hydrated_element)

        return hydrated

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

    def _hydrate_list_items(
        self,
        element: dict[str, Any],
        values: list[Any],
    ) -> list[Any]:
        template_items = element.get("value", [])
        template_item = template_items[0] if template_items else None

        if template_item is None:
            template_item = self._build_list_item_template(element)

        if template_item is None:
            return values

        hydrated_items: list[Any] = []
        for item_value in values:
            item_template = json.loads(json.dumps(template_item))
            hydrated_items.append(self._hydrate_element_value(item_template, item_value))

        return hydrated_items

    def _hydrate_element_value(
        self,
        element: dict[str, Any],
        value: Any,
    ) -> dict[str, Any]:
        element_type = element.get("modelType", {}).get("name", "Property")

        if element_type == "Property":
            element["value"] = "" if value is None else str(value)
        elif element_type == "MultiLanguageProperty":
            if isinstance(value, dict):
                element["value"] = [
                    {"language": lang, "text": text} for lang, text in value.items()
                ]
        elif element_type == "SubmodelElementCollection":
            if isinstance(value, dict):
                nested = element.get("value", [])
                element["value"] = self._hydrate_elements(nested, value)
        elif element_type == "SubmodelElementList":
            if isinstance(value, list):
                element["value"] = self._hydrate_list_items(element, value)
        elif element_type == "Range":
            if isinstance(value, dict):
                element["min"] = value.get("min")
                element["max"] = value.get("max")
        elif element_type == "File" and isinstance(value, dict):
            element["contentType"] = value.get("contentType", "")
            element["value"] = value.get("value", "")
        elif element_type == "ReferenceElement" and isinstance(value, dict):
            element["value"] = {
                "type": value.get("type", "ModelReference"),
                "keys": value.get("keys", []),
            }
        elif element_type == "Entity" and isinstance(value, dict):
            element["entityType"] = value.get("entityType", element.get("entityType"))
            if value.get("globalAssetId") is not None:
                element["globalAssetId"] = value.get("globalAssetId")
            statements = element.get("statements", [])
            statement_data = value.get("statements", {})
            if isinstance(statement_data, dict):
                element["statements"] = self._hydrate_elements(statements, statement_data)
        elif element_type == "RelationshipElement" and isinstance(value, dict):
            if value.get("first") is not None:
                element["first"] = value.get("first")
            if value.get("second") is not None:
                element["second"] = value.get("second")
        elif element_type == "AnnotatedRelationshipElement" and isinstance(value, dict):
            if value.get("first") is not None:
                element["first"] = value.get("first")
            if value.get("second") is not None:
                element["second"] = value.get("second")
            annotations = element.get("annotations", [])
            annotation_data = value.get("annotations", {})
            if isinstance(annotation_data, dict):
                element["annotations"] = self._hydrate_elements(annotations, annotation_data)

        return element

    def _calculate_digest(self, aas_env: dict[str, Any]) -> str:
        """
        Calculate SHA-256 digest of canonicalized AAS environment.

        Uses deterministic JSON serialization for consistent hashing.
        """
        # Canonical JSON: sorted keys, no extra whitespace
        canonical = json.dumps(aas_env, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()
