"""Tests for OPC UA ABAC resource context builders."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4


def test_opcua_resource_contexts_include_tenant_id() -> None:
    from app.core.security.resource_context import (
        build_opcua_mapping_resource_context,
        build_opcua_nodeset_resource_context,
        build_opcua_source_resource_context,
    )

    tenant_id = uuid4()
    source = SimpleNamespace(id=uuid4(), tenant_id=tenant_id, created_by="publisher-a")
    nodeset = SimpleNamespace(id=uuid4(), tenant_id=tenant_id, created_by="publisher-a")
    mapping = SimpleNamespace(id=uuid4(), tenant_id=tenant_id, created_by="publisher-a")

    assert build_opcua_source_resource_context(source)["tenant_id"] == str(tenant_id)
    assert build_opcua_nodeset_resource_context(nodeset)["tenant_id"] == str(tenant_id)
    assert build_opcua_mapping_resource_context(mapping)["tenant_id"] == str(tenant_id)
