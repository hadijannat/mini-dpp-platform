"""
DPP (Digital Product Passport) Core Service.
Handles DPP lifecycle, revision management, and data hydration.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import DPP, DPPRevision, DPPStatus, RevisionState, Template
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
            select(DPPRevision).where(
                DPPRevision.id == dpp.current_published_revision_id
            )
        )
        return result.scalar_one_or_none()

    async def update_submodel(
        self,
        dpp_id: UUID,
        template_key: str,
        submodel_data: dict[str, Any],
        updated_by_subject: str,
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
            raise ValueError(f"Template {template_key} not found")

        # Find submodel by semantic ID
        target_semantic_id = template.semantic_id
        updated = False

        for i, submodel in enumerate(submodels):
            sm_semantic_id = submodel.get("semanticId", {}).get("keys", [{}])[0].get("value", "")
            if target_semantic_id in sm_semantic_id:
                # Hydrate the submodel with new data
                submodels[i] = await self._hydrate_submodel(
                    template,
                    submodel,
                    submodel_data,
                )
                updated = True
                break

        if not updated:
            raise ValueError(f"Submodel {template_key} not found in DPP")

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
                logger.warning("template_not_found", template_key=template_key)
                continue

            # Clone template submodel(s)
            template_submodels = template.template_json.get("submodels", [])

            for sm_template in template_submodels:
                # Create instance from template
                submodel_id = f"urn:dpp:sm:{template_key}:{asset_ids.get('manufacturerPartId', 'unknown')}"

                submodel = json.loads(json.dumps(sm_template))
                submodel["id"] = submodel_id

                # Apply initial data if provided
                if template_key in initial_data:
                    submodel = await self._hydrate_submodel(
                        template,
                        submodel,
                        initial_data[template_key],
                    )

                aas_env["submodels"].append(submodel)

                # Add reference to AAS
                aas["submodelRefs"].append({
                    "type": "ModelReference",
                    "keys": [{"type": "Submodel", "value": submodel_id}],
                })

            # Include concept descriptions
            template_cds = template.template_json.get("conceptDescriptions", [])
            aas_env["conceptDescriptions"].extend(template_cds)

        aas_env["assetAdministrationShells"].append(aas)

        return aas_env

    async def _hydrate_submodel(
        self,
        template: Template,
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
            element_type = element.get("modelType", {}).get("name", "Property")

            hydrated_element = json.loads(json.dumps(element))

            if id_short in data:
                value = data[id_short]

                if element_type == "Property":
                    hydrated_element["value"] = str(value)
                elif element_type == "MultiLanguageProperty":
                    if isinstance(value, dict):
                        hydrated_element["value"] = [
                            {"language": lang, "text": text}
                            for lang, text in value.items()
                        ]
                elif element_type == "SubmodelElementCollection":
                    if isinstance(value, dict):
                        nested = element.get("value", [])
                        hydrated_element["value"] = self._hydrate_elements(nested, value)
                elif element_type == "Range":
                    if isinstance(value, dict):
                        hydrated_element["min"] = value.get("min")
                        hydrated_element["max"] = value.get("max")
                elif element_type == "File":
                    if isinstance(value, dict):
                        hydrated_element["contentType"] = value.get("contentType", "")
                        hydrated_element["value"] = value.get("value", "")

            hydrated.append(hydrated_element)

        return hydrated

    def _calculate_digest(self, aas_env: dict[str, Any]) -> str:
        """
        Calculate SHA-256 digest of canonicalized AAS environment.

        Uses deterministic JSON serialization for consistent hashing.
        """
        # Canonical JSON: sorted keys, no extra whitespace
        canonical = json.dumps(aas_env, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()
