import pytest

from src.data.repositories.jobs import JobsRepository
from src.data.repositories.runs import RunsRepository


@pytest.mark.asyncio(loop_scope="session")
async def test_jobs_upsert_is_idempotent(db_session):
    repo = JobsRepository(db_session)
    row_a = await repo.upsert(
        source="linkedin",
        source_id="x1",
        title="Eng",
        company="Co",
        jd_text="desc",
        url=None,
        match_score=0.8,
    )
    await db_session.commit()
    row_b = await repo.upsert(
        source="linkedin",
        source_id="x1",
        title="Eng",
        company="Co",
        jd_text="desc",
        url=None,
        match_score=0.9,
    )
    await db_session.commit()
    assert row_a.id == row_b.id
    assert row_b.match_score == 0.9


@pytest.mark.asyncio(loop_scope="session")
async def test_runs_get_or_create_idempotent_on_correlation(db_session):
    repo = RunsRepository(db_session)
    run1, created1 = await repo.get_or_create(kind="scrape", correlation_id="c1")
    await db_session.commit()
    run2, created2 = await repo.get_or_create(kind="scrape", correlation_id="c1")
    assert created1 is True
    assert created2 is False
    assert run1.id == run2.id


@pytest.mark.asyncio(loop_scope="session")
async def test_runs_different_kind_same_corr_id_are_distinct(db_session):
    repo = RunsRepository(db_session)
    a, _ = await repo.get_or_create(kind="scrape", correlation_id="c1")
    b, _ = await repo.get_or_create(kind="tailor", correlation_id="c1")
    await db_session.commit()
    assert a.id != b.id
