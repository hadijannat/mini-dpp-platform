from types import SimpleNamespace

from app.modules.dpps.service import DPPService


def test_audit_revision_binding_compatibility_allows_submodel_id_source() -> None:
    service = DPPService.__new__(DPPService)
    revision = SimpleNamespace(
        aas_env_json={
            "submodels": [
                {
                    "id": "urn:dpp:sm:digital-nameplate:publish-2026-026566",
                    "idShort": "Nameplate",
                    "semanticId": {
                        "keys": [
                            {
                                "type": "GlobalReference",
                                "value": "urn:non-standard:semantic",
                            }
                        ]
                    },
                }
            ]
        },
        template_provenance={},
    )
    templates = [
        SimpleNamespace(
            template_key="digital-nameplate",
            semantic_id="https://admin-shell.io/idta/nameplate/3/0/Nameplate",
        )
    ]

    audit = DPPService.audit_revision_binding_compatibility(
        service,
        revision=revision,
        templates=templates,
    )

    assert audit["ok"] is True
    assert audit["issues"] == []


def test_audit_revision_binding_compatibility_blocks_unresolved_binding() -> None:
    service = DPPService.__new__(DPPService)
    revision = SimpleNamespace(
        aas_env_json={
            "submodels": [
                {
                    "id": "urn:dpp:sm:unknown-template:publish-2026-026566",
                    "idShort": "UnmappedSubmodel",
                    "semanticId": {
                        "keys": [
                            {
                                "type": "GlobalReference",
                                "value": "urn:non-standard:semantic",
                            }
                        ]
                    },
                }
            ]
        },
        template_provenance={},
    )
    templates = [
        SimpleNamespace(
            template_key="digital-nameplate",
            semantic_id="https://admin-shell.io/idta/nameplate/3/0/Nameplate",
        )
    ]

    audit = DPPService.audit_revision_binding_compatibility(
        service,
        revision=revision,
        templates=templates,
    )

    assert audit["ok"] is False
    assert audit["issues"][0]["code"] == "unresolved_binding"
