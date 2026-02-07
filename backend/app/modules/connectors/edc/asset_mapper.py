"""
Map DPP data to EDC asset payloads.

Converts a published DPP + revision into an ``EDCAsset`` whose DataAddress
points at the platform's public DPP API so data consumers can access
the passport through the EDC data plane.
"""

from __future__ import annotations

from typing import Any

from app.db.models import DPP, DPPRevision
from app.modules.aas.references import extract_semantic_id_str
from app.modules.connectors.edc.models import DataAddress, EDCAsset


def map_dpp_to_edc_asset(
    dpp: DPP,
    revision: DPPRevision,
    public_api_base_url: str,
) -> EDCAsset:
    """
    Build an EDC asset from a published DPP.

    Args:
        dpp: The DPP entity.
        revision: The published revision containing the AAS environment.
        public_api_base_url: Root URL of the platform's public API
            (e.g. ``https://dpp-platform.dev/api/v1/public``).

    Returns:
        An ``EDCAsset`` ready to be created via the management API.
    """
    asset_id = f"dpp-{dpp.id}"

    # Collect semantic IDs from all submodels in this DPP
    aas_env: dict[str, Any] = revision.aas_env_json
    semantic_ids: list[str] = []
    submodel_id_shorts: list[str] = []
    for submodel in aas_env.get("submodels", []):
        sem_id = extract_semantic_id_str(submodel)
        if sem_id:
            semantic_ids.append(sem_id)
        id_short = submodel.get("idShort", "")
        if id_short:
            submodel_id_shorts.append(id_short)

    # Build human-readable name from asset IDs
    manufacturer_part = dpp.asset_ids.get("manufacturerPartId", "")
    serial_number = dpp.asset_ids.get("serialNumber", "")
    display_name = f"DPP {manufacturer_part}"
    if serial_number:
        display_name = f"{display_name} / {serial_number}"

    properties: dict[str, Any] = {
        "name": display_name,
        "description": f"Digital Product Passport for {manufacturer_part}",
        "contenttype": "application/json",
        "dpp:id": str(dpp.id),
        "dpp:revisionNo": revision.revision_no,
        "dpp:globalAssetId": dpp.asset_ids.get("globalAssetId", ""),
        "dpp:manufacturerPartId": manufacturer_part,
        "dpp:semanticIds": semantic_ids,
        "dpp:submodelIdShorts": submodel_id_shorts,
    }

    # DataAddress points to the platform's public DPP endpoint
    base = public_api_base_url.rstrip("/")
    data_address = DataAddress(
        type="HttpData",
        base_url=f"{base}/dpps/{dpp.id}",
        proxy_body=False,
        proxy_path=True,
        proxy_query_params=True,
    )

    return EDCAsset(
        asset_id=asset_id,
        properties=properties,
        data_address=data_address,
    )
