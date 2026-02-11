"""Unit tests for MinIO-backed DPP attachment service."""

from __future__ import annotations

import io
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile

from app.db.models import DPPAttachment
from app.modules.dpps.attachment_service import AttachmentNotFoundError, AttachmentService


class _ObjectResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def close(self) -> None:
        return None

    def release_conn(self) -> None:
        return None


class FakeMinio:
    def __init__(self) -> None:
        self._buckets: set[str] = set()
        self._objects: dict[tuple[str, str], bytes] = {}

    def bucket_exists(self, bucket: str) -> bool:
        return bucket in self._buckets

    def make_bucket(self, bucket: str) -> None:
        self._buckets.add(bucket)

    def put_object(
        self,
        bucket: str,
        object_key: str,
        data: io.BytesIO,
        length: int,
        content_type: str,
        metadata: dict[str, str],
    ) -> None:
        assert content_type
        assert metadata.get("sha256")
        self._objects[(bucket, object_key)] = data.read(length)

    def get_object(self, bucket: str, object_key: str) -> _ObjectResponse:
        key = (bucket, object_key)
        if key not in self._objects:
            raise FileNotFoundError(object_key)
        return _ObjectResponse(self._objects[key])

    def remove_object(self, bucket: str, object_key: str) -> None:
        self._objects.pop((bucket, object_key), None)


class FakeResult:
    def __init__(self, value: DPPAttachment | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> DPPAttachment | None:
        return self._value


class FakeSession:
    def __init__(self) -> None:
        self.attachments: dict[tuple[UUID, UUID, UUID], DPPAttachment] = {}

    def add(self, instance: object) -> None:
        if isinstance(instance, DPPAttachment):
            key = (instance.tenant_id, instance.dpp_id, instance.id)
            self.attachments[key] = instance

    async def flush(self) -> None:
        return None

    async def execute(self, statement):  # type: ignore[no-untyped-def]
        params = statement.compile().params

        def _pick(prefix: str):
            for key, value in params.items():
                if key.startswith(prefix):
                    return value
            return None

        attachment_id = _pick("id")
        tenant_id = _pick("tenant_id")
        dpp_id = _pick("dpp_id")
        if attachment_id is None or tenant_id is None or dpp_id is None:
            return FakeResult(None)

        key = (tenant_id, dpp_id, attachment_id)
        return FakeResult(self.attachments.get(key))


@pytest.mark.asyncio()
async def test_attachment_service_upload_and_download_roundtrip() -> None:
    tenant_id = uuid4()
    dpp_id = uuid4()
    owner = "owner-sub"
    session = FakeSession()
    client = FakeMinio()

    service = AttachmentService(session, client=client)  # type: ignore[arg-type]
    upload = UploadFile(filename="manual.pdf", file=io.BytesIO(b"pdf-content"))

    uploaded = await service.upload_attachment(
        tenant_id=tenant_id,
        dpp_id=dpp_id,
        upload_file=upload,
        created_by_subject=owner,
        requested_content_type="application/pdf",
    )

    assert uploaded.size_bytes == len(b"pdf-content")
    assert uploaded.content_type == "application/pdf"

    attachment, payload = await service.download_attachment_bytes(
        tenant_id=tenant_id,
        dpp_id=dpp_id,
        attachment_id=uploaded.attachment_id,
    )

    assert payload == b"pdf-content"
    assert attachment.filename == "manual.pdf"


@pytest.mark.asyncio()
async def test_attachment_service_rejects_invalid_mime_type() -> None:
    session = FakeSession()
    client = FakeMinio()
    service = AttachmentService(session, client=client)  # type: ignore[arg-type]

    upload = UploadFile(filename="image.bin", file=io.BytesIO(b"data"))

    with pytest.raises(ValueError, match="Invalid MIME type"):
        await service.upload_attachment(
            tenant_id=uuid4(),
            dpp_id=uuid4(),
            upload_file=upload,
            created_by_subject="owner-sub",
            requested_content_type="not a mime",
        )


@pytest.mark.asyncio()
async def test_attachment_service_rejects_oversized_upload() -> None:
    session = FakeSession()
    client = FakeMinio()
    service = AttachmentService(session, client=client)  # type: ignore[arg-type]
    service._settings = SimpleNamespace(  # type: ignore[assignment]
        attachments_max_upload_bytes=4,
        mime_validation_regex=service._settings.mime_validation_regex,
        minio_bucket_attachments=service._settings.minio_bucket_attachments,
    )

    upload = UploadFile(filename="manual.pdf", file=io.BytesIO(b"12345"))
    with pytest.raises(ValueError, match="max upload size"):
        await service.upload_attachment(
            tenant_id=uuid4(),
            dpp_id=uuid4(),
            upload_file=upload,
            created_by_subject="owner-sub",
            requested_content_type="application/pdf",
        )


@pytest.mark.asyncio()
async def test_attachment_service_enforces_tenant_and_dpp_scoping() -> None:
    tenant_id = uuid4()
    dpp_id = uuid4()
    other_tenant_id = uuid4()
    session = FakeSession()
    client = FakeMinio()
    service = AttachmentService(session, client=client)  # type: ignore[arg-type]

    upload = UploadFile(filename="manual.pdf", file=io.BytesIO(b"payload"))
    uploaded = await service.upload_attachment(
        tenant_id=tenant_id,
        dpp_id=dpp_id,
        upload_file=upload,
        created_by_subject="owner-sub",
        requested_content_type="application/pdf",
    )

    with pytest.raises(AttachmentNotFoundError):
        await service.get_attachment_metadata(
            tenant_id=other_tenant_id,
            dpp_id=dpp_id,
            attachment_id=uploaded.attachment_id,
        )


@pytest.mark.asyncio()
async def test_attachment_service_reports_missing_object_content() -> None:
    tenant_id = uuid4()
    dpp_id = uuid4()
    session = FakeSession()
    client = FakeMinio()
    service = AttachmentService(session, client=client)  # type: ignore[arg-type]

    upload = UploadFile(filename="manual.pdf", file=io.BytesIO(b"payload"))
    uploaded = await service.upload_attachment(
        tenant_id=tenant_id,
        dpp_id=dpp_id,
        upload_file=upload,
        created_by_subject="owner-sub",
        requested_content_type="application/pdf",
    )

    attachment = await service.get_attachment_metadata(
        tenant_id=tenant_id,
        dpp_id=dpp_id,
        attachment_id=uploaded.attachment_id,
    )
    client.remove_object(service._bucket, attachment.object_key)  # type: ignore[arg-type]

    with pytest.raises(AttachmentNotFoundError):
        await service.download_attachment_bytes(
            tenant_id=tenant_id,
            dpp_id=dpp_id,
            attachment_id=uploaded.attachment_id,
        )
