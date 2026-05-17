from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.job import Job


class JobsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        *,
        source: str,
        source_id: str,
        title: str,
        company: str,
        jd_text: str,
        url: str | None,
        match_score: float | None = None,
        score_breakdown: dict | None = None,
    ) -> Job:
        stmt = (
            insert(Job)
            .values(
                source=source,
                source_id=source_id,
                title=title,
                company=company,
                url=url,
                jd_text=jd_text,
                match_score=match_score,
                score_breakdown=score_breakdown,
            )
            .on_conflict_do_update(
                index_elements=["source", "source_id"],
                set_={
                    "title": title,
                    "company": company,
                    "url": url,
                    "jd_text": jd_text,
                    "match_score": match_score,
                    "score_breakdown": score_breakdown,
                },
            )
            .returning(Job)
        )
        result = await self.session.execute(
            stmt, execution_options={"populate_existing": True}
        )
        return result.scalar_one()

    async def get_by_id(self, job_id) -> Job | None:
        return await self.session.get(Job, job_id)

    async def list_by_status(self, status: str, limit: int = 50) -> list[Job]:
        stmt = select(Job).where(Job.status == status).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars())

    async def list_paginated(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        status: str | None = None,
        source: str | None = None,
    ) -> tuple[list[Job], int]:
        from sqlalchemy import func, select

        stmt = select(Job)
        count_stmt = select(func.count()).select_from(Job)
        if status:
            stmt = stmt.where(Job.status == status)
            count_stmt = count_stmt.where(Job.status == status)
        if source:
            stmt = stmt.where(Job.source == source)
            count_stmt = count_stmt.where(Job.source == source)
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()
        res = await self.session.execute(stmt)
        return list(res.scalars()), total
