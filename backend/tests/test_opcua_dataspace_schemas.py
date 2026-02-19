"""Tests for dataspace publication schemas."""

import uuid


def test_dataspace_publish_request():
    from app.modules.opcua.schemas import DataspacePublishRequest

    req = DataspacePublishRequest(dpp_id=uuid.uuid4(), target="catena-x")
    assert req.target == "catena-x"


def test_dataspace_publication_job_response():
    from app.modules.opcua.schemas import DataspacePublicationJobResponse

    assert DataspacePublicationJobResponse.model_config.get("from_attributes") is True
