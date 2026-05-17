from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.job import JobArtifact


class JobArtifactsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_latest(self, job_id: uuid.UUID, kind: Literal["cover_letter", "resume_text"]) -> JobArtifact | None:
        stmt = (
            select(JobArtifact)
            .where(JobArtifact.job_id == job_id, JobArtifact.kind == kind)
            .order_by(desc(JobArtifact.version))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _next_version(self, job_id: uuid.UUID, kind: str) -> int:
        stmt = select(func.max(JobArtifact.version)).where(
            JobArtifact.job_id == job_id, JobArtifact.kind == kind
        )
        result = await self.session.execute(stmt)
        current = result.scalar_one_or_none()
        return (current or 0) + 1

    async def create(
        self,
        *,
        job_id: uuid.UUID,
        kind: Literal["cover_letter", "resume_text"],
        text: str,
        file_path: str = "",
    ) -> JobArtifact:
        version = await self._next_version(job_id, kind)
        row = JobArtifact(job_id=job_id, kind=kind, text=text, file_path=file_path, version=version)
        self.session.add(row)
        await self.session.flush()
        return row
