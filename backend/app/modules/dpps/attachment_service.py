"""Attachment storage service backed by MinIO."""

from __future__ import annotations

import asyncio
import hashlib
import io
import mimetypes
from dataclasses import dataclass
from uuid import UUID, uuid4

from fastapi import UploadFile
from minio import Minio
from minio.error import S3Error
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import DPPAttachment
from app.modules.dpps.mime import validate_mime_type


class AttachmentNotFoundError(FileNotFoundError):
    """Attachment metadata or object content could not be found."""


@dataclass(frozen=True)
class AttachmentPayload:
    """Stored attachment metadata returned by upload operations."""

    attachment_id: UUID
    content_type: str
    size_bytes: int


class AttachmentService:
    """Store and retrieve DPP attachments with tenant-scoped isolation."""

    def __init__(self, session: AsyncSession, client: Minio | None = None) -> None:
        self._session = session
        self._settings = get_settings()
        self._client = client or Minio(
            endpoint=self._settings.minio_endpoint,
            access_key=self._settings.minio_access_key,
            secret_key=self._settings.minio_secret_key,
            secure=self._settings.minio_secure,
        )
        self._bucket = self._settings.minio_bucket_attachments

    async def upload_attachment(
        self,
        *,
        tenant_id: UUID,
        dpp_id: UUID,
        upload_file: UploadFile,
        created_by_subject: str,
        requested_content_type: str | None,
    ) -> AttachmentPayload:
        filename = self._sanitize_filename(upload_file.filename or "attachment.bin")
        content_type = self._resolve_content_type(
            requested_content_type=requested_content_type,
            upload_content_type=upload_file.content_type,
            filename=filename,
        )

        sha256 = hashlib.sha256()
        payload = io.BytesIO()
        size_bytes = 0
        max_bytes = self._settings.attachments_max_upload_bytes

        while True:
            chunk = await upload_file.read(1024 * 1024)
            if not chunk:
                break
            size_bytes += len(chunk)
            if size_bytes > max_bytes:
                raise ValueError(f"Attachment exceeds max upload size ({max_bytes} bytes)")
            sha256.update(chunk)
            payload.write(chunk)

        if size_bytes == 0:
            raise ValueError("Attachment is empty")

        attachment_id = uuid4()
        object_key = f"{tenant_id}/{dpp_id}/{attachment_id}/{filename}"

        await self._ensure_bucket()
        payload.seek(0)

        await asyncio.to_thread(
            self._client.put_object,
            self._bucket,
            object_key,
            payload,
            size_bytes,
            content_type=content_type,
            metadata={
                "tenant_id": str(tenant_id),
                "dpp_id": str(dpp_id),
                "sha256": sha256.hexdigest(),
            },
        )

        attachment = DPPAttachment(
            id=attachment_id,
            tenant_id=tenant_id,
            dpp_id=dpp_id,
            filename=filename,
            object_key=object_key,
            content_type=content_type,
            size_bytes=size_bytes,
            sha256=sha256.hexdigest(),
            created_by_subject=created_by_subject,
        )

        try:
            self._session.add(attachment)
            await self._session.flush()
        except Exception:
            await asyncio.to_thread(self._client.remove_object, self._bucket, object_key)
            raise

        return AttachmentPayload(
            attachment_id=attachment.id,
            content_type=attachment.content_type,
            size_bytes=attachment.size_bytes,
        )

    async def get_attachment_metadata(
        self,
        *,
        tenant_id: UUID,
        dpp_id: UUID,
        attachment_id: UUID,
    ) -> DPPAttachment:
        result = await self._session.execute(
            select(DPPAttachment).where(
                DPPAttachment.id == attachment_id,
                DPPAttachment.tenant_id == tenant_id,
                DPPAttachment.dpp_id == dpp_id,
            )
        )
        attachment = result.scalar_one_or_none()
        if attachment is None:
            raise AttachmentNotFoundError("Attachment not found")
        return attachment

    async def download_attachment_bytes(
        self,
        *,
        tenant_id: UUID,
        dpp_id: UUID,
        attachment_id: UUID,
    ) -> tuple[DPPAttachment, bytes]:
        attachment = await self.get_attachment_metadata(
            tenant_id=tenant_id,
            dpp_id=dpp_id,
            attachment_id=attachment_id,
        )

        try:
            data = await asyncio.to_thread(self._read_object_bytes, attachment.object_key)
        except FileNotFoundError as exc:
            raise AttachmentNotFoundError("Attachment object not found") from exc
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                raise AttachmentNotFoundError("Attachment object not found") from exc
            raise

        return attachment, data

    def _read_object_bytes(self, object_key: str) -> bytes:
        response = self._client.get_object(self._bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def _ensure_bucket(self) -> None:
        exists = await asyncio.to_thread(self._client.bucket_exists, self._bucket)
        if exists:
            return
        await asyncio.to_thread(self._client.make_bucket, self._bucket)

    def _resolve_content_type(
        self,
        *,
        requested_content_type: str | None,
        upload_content_type: str | None,
        filename: str,
    ) -> str:
        guessed = mimetypes.guess_type(filename, strict=False)[0]
        raw = requested_content_type or upload_content_type or guessed
        normalized = validate_mime_type(
            raw,
            pattern=self._settings.mime_validation_regex,
            allow_empty=False,
        )
        if not normalized:
            raise ValueError("Attachment content type is required")
        return normalized

    def _sanitize_filename(self, filename: str) -> str:
        keep = [ch for ch in filename if ch.isalnum() or ch in {"-", "_", "."}]
        sanitized = "".join(keep).strip(".")
        return sanitized or "attachment.bin"
