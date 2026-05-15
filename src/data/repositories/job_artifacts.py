from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy import desc, select
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

    async def create(
        self,
        *,
        job_id: uuid.UUID,
        kind: Literal["cover_letter", "resume_text"],
        text: str,
        file_path: str = "",
    ) -> JobArtifact:
        row = JobArtifact(job_id=job_id, kind=kind, text=text, file_path=file_path)
        self.session.add(row)
        await self.session.flush()
        return row
