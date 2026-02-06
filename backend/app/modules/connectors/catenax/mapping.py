"""
Mapping utilities for converting DPP data to Catena-X DTR descriptor format.
"""

from typing import Any
from urllib.parse import quote

from app.core.config import get_settings
from app.db.models import DPP, DPPRevision
from app.modules.aas.references import extract_semantic_id_str
from app.modules.connectors.catenax.dtr_client import ShellDescriptor

# Mapping from IDTA AAS semantic IDs to Catena-X SAMM URNs.
# When registering submodels in a Catena-X DTR, descriptors should carry
# SAMM-based semantic IDs so that data consumers can discover submodels
# using the DTR's semantic ID search.
_AAS_TO_SAMM: dict[str, str] = {
    "https://admin-shell.io/zvei/nameplate/2/0/Nameplate": (
        "urn:samm:io.catenax.serial_part:3.0.0#SerialPart"
    ),
    "https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/1/0": (
        "urn:samm:io.catenax.pcf:6.0.0#Pcf"
    ),
    "https://admin-shell.io/idta/HierarchicalStructures/1/1/Submodel": (
        "urn:samm:io.catenax.single_level_bom_as_built:3.0.0#SingleLevelBomAsBuilt"
    ),
    "https://admin-shell.io/idta/BatteryPassport/GeneralProductInformation/1/0": (
        "urn:samm:io.catenax.battery.battery_pass:6.0.0#BatteryPass"
    ),
}


def translate_semantic_id_for_catenax(aas_semantic_id: str) -> str:
    """Translate an IDTA AAS semantic ID to its Catena-X SAMM URN equivalent.

    Returns the SAMM URN if a mapping exists, otherwise returns
    the original AAS semantic ID unchanged.
    """
    return _AAS_TO_SAMM.get(aas_semantic_id, aas_semantic_id)


# DTR requires at least one security attribute entry on protocolInformation.
DEFAULT_SECURITY_ATTRIBUTES = [
    {"type": "NONE", "key": "none", "value": "none"},
]


def build_shell_descriptor(
    dpp: DPP,
    revision: DPPRevision,
    submodel_base_url: str,
    edc_dsp_endpoint: str | None = None,
) -> ShellDescriptor:
    """
    Build a Catena-X shell descriptor from DPP data.

    Args:
        dpp: The DPP entity
        revision: The revision to use for descriptor content
        submodel_base_url: Base URL where submodel endpoints are exposed
        edc_dsp_endpoint: Optional DSP endpoint metadata for data plane access

    Returns:
        ShellDescriptor ready for DTR registration
    """
    settings = get_settings()

    # Build global asset ID
    global_asset_id = dpp.asset_ids.get("globalAssetId", f"urn:uuid:{dpp.id}")

    # Build specific asset IDs
    specific_asset_ids = []
    for key, value in dpp.asset_ids.items():
        if key != "globalAssetId":
            specific_asset_ids.append(
                {
                    "name": key,
                    "value": str(value),
                    "externalSubjectId": {
                        "type": "ExternalReference",
                        "keys": [
                            {
                                "type": "GlobalReference",
                                "value": settings.keycloak_client_id or "dpp-platform",
                            }
                        ],
                    },
                }
            )

    # Build submodel descriptors
    submodel_descriptors = []
    aas_env = revision.aas_env_json

    for submodel in aas_env.get("submodels", []):
        submodel_id = submodel.get("id", "")
        id_short = submodel.get("idShort", "")
        aas_semantic_id = extract_semantic_id_str(submodel)
        semantic_id = translate_semantic_id_for_catenax(aas_semantic_id)

        # Build endpoint URL
        # Catena-X requires $value serialization
        encoded_submodel_id = quote(str(submodel_id), safe="")
        endpoint_url = f"{submodel_base_url}/submodels/{encoded_submodel_id}/$value"

        descriptor: dict[str, Any] = {
            "id": submodel_id,
            "idShort": id_short,
            "semanticId": {
                "type": "ExternalReference",
                "keys": [
                    {
                        "type": "GlobalReference",
                        "value": semantic_id,
                    }
                ],
            },
            "endpoints": [
                {
                    "interface": "SUBMODEL-3.0",
                    "protocolInformation": {
                        "href": endpoint_url,
                        "endpointProtocol": "HTTP",
                        "endpointProtocolVersion": ["1.1"],
                        "securityAttributes": DEFAULT_SECURITY_ATTRIBUTES,
                    },
                }
            ],
        }

        # Add EDC-specific fields if configured
        if edc_dsp_endpoint:
            descriptor["endpoints"][0]["protocolInformation"].update(
                {
                    "subprotocol": "DSP",
                    "subprotocolBody": f"id={encoded_submodel_id};dspEndpoint={edc_dsp_endpoint}",
                    "subprotocolBodyEncoding": "plain",
                }
            )

        submodel_descriptors.append(descriptor)

    return ShellDescriptor(
        id=f"urn:uuid:{dpp.id}",
        id_short=f"DPP_{dpp.asset_ids.get('manufacturerPartId', str(dpp.id)[:8])}",
        global_asset_id=global_asset_id,
        specific_asset_ids=specific_asset_ids,
        submodel_descriptors=submodel_descriptors,
    )


