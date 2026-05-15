from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.application import Application
from src.data.models.job import Job


async def find_application_by_company(session: AsyncSession, company: str) -> Application | None:
    """Return the most-recently-submitted Application whose Job.company fuzzy-matches `company`."""
    if not company or not company.strip():
        return None
    pattern = f"%{company.strip().lower()}%"
    stmt = (
        select(Application)
        .join(Job, Application.job_id == Job.id)
        .where(func.lower(Job.company).like(pattern))
        .order_by(Application.submitted_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
