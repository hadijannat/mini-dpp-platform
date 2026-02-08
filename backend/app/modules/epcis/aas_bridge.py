"""Map EPCIS events into an IDTA Traceability AAS submodel.

Produces a pure-dict AAS Submodel structure (no BaSyx dependency)
that can be injected into an AAS environment for export.
"""

from __future__ import annotations

from typing import Any

from .schemas import EPCISEventResponse

TRACEABILITY_SEMANTIC_ID = "https://admin-shell.io/idta/Traceability/1/0"
TRACEABILITY_ID_SHORT = "Traceability"


def build_traceability_submodel(
    events: list[EPCISEventResponse],
) -> dict[str, Any] | None:
    """Convert EPCIS events into an AAS Traceability submodel dict.

    Returns ``None`` if the event list is empty (don't inject an empty submodel).
    """
    if not events:
        return None

    elements: list[dict[str, Any]] = []
    for idx, event in enumerate(events):
        props: list[dict[str, Any]] = [
            _property("EventType", event.event_type),
            _property("EventTime", event.event_time.isoformat()),
        ]
        if event.action:
            props.append(_property("Action", event.action))
        if event.biz_step:
            props.append(_property("BizStep", event.biz_step))
        if event.disposition:
            props.append(_property("Disposition", event.disposition))
        if event.read_point:
            props.append(_property("ReadPoint", event.read_point))
        if event.biz_location:
            props.append(_property("BizLocation", event.biz_location))

        # Nest payload data (EPC lists, quantities, etc.)
        payload_props = _build_payload_properties(event.payload)
        if payload_props:
            props.append(
                {
                    "modelType": "SubmodelElementCollection",
                    "idShort": "Payload",
                    "value": payload_props,
                }
            )

        collection: dict[str, Any] = {
            "modelType": "SubmodelElementCollection",
            "idShort": f"Event{idx + 1:03d}",
            "value": props,
        }
        elements.append(collection)

    return {
        "modelType": "Submodel",
        "idShort": TRACEABILITY_ID_SHORT,
        "id": TRACEABILITY_SEMANTIC_ID,
        "semanticId": {
            "type": "ExternalReference",
            "keys": [
                {
                    "type": "GlobalReference",
                    "value": TRACEABILITY_SEMANTIC_ID,
                }
            ],
        },
        "submodelElements": elements,
    }


def _property(id_short: str, value: str) -> dict[str, Any]:
    """Build an AAS Property element dict."""
    return {
        "modelType": "Property",
        "idShort": id_short,
        "valueType": "xs:string",
        "value": value,
    }


def _build_payload_properties(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert EPCIS payload fields into AAS Property elements."""
    props: list[dict[str, Any]] = []

    # EPC lists
    for key in ("epcList", "childEPCs", "inputEPCList", "outputEPCList"):
        epcs = payload.get(key)
        if isinstance(epcs, list) and epcs:
            props.append(_property(key, ", ".join(str(e) for e in epcs)))

    # Parent ID
    parent = payload.get("parentID")
    if parent:
        props.append(_property("ParentID", str(parent)))

    # Transformation ID
    transform = payload.get("transformationID")
    if transform:
        props.append(_property("TransformationID", str(transform)))

    return props
