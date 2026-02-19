"""Dataspace publication service — DTR + EDC publication workflow."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DataspacePublicationJob, DataspacePublicationStatus

logger = logging.getLogger(__name__)


class DataspacePublicationService:
    """Manages publication job lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_publication_job(
        self,
        tenant_id: UUID,
        dpp_id: UUID,
        target: str = "catena-x",
    ) -> DataspacePublicationJob:
        """Create a new publication job in QUEUED state."""
        job = DataspacePublicationJob(
            tenant_id=tenant_id,
            dpp_id=dpp_id,
            status=DataspacePublicationStatus.QUEUED,
            target=target,
            artifact_refs={},
        )
        self._session.add(job)
        await self._session.flush()
        return job

    async def get_publication_job(
        self,
        job_id: UUID,
        tenant_id: UUID,
    ) -> DataspacePublicationJob | None:
        job = await self._session.get(DataspacePublicationJob, job_id)
        if job and str(job.tenant_id) == str(tenant_id):
            return job
        return None

    async def list_publication_jobs(
        self,
        tenant_id: UUID,
        *,
        dpp_id: UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[DataspacePublicationJob], int]:
        base = select(DataspacePublicationJob).where(DataspacePublicationJob.tenant_id == tenant_id)
        if dpp_id:
            base = base.where(DataspacePublicationJob.dpp_id == dpp_id)
        count_q = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_q)).scalar_one()
        rows_q = (
            base.order_by(DataspacePublicationJob.created_at.desc()).offset(offset).limit(limit)
        )
        rows = (await self._session.execute(rows_q)).scalars().all()
        return list(rows), total

    async def retry_publication_job(self, job: DataspacePublicationJob) -> DataspacePublicationJob:
        if job.status != DataspacePublicationStatus.FAILED:
            raise ValueError("Only failed jobs can be retried")
        job.status = DataspacePublicationStatus.QUEUED
        job.error = None
        await self._session.flush()
        return job
