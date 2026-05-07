import uuid
import pytest
from src.data.models.run import Run
from src.data.repositories.runs import RunsRepository


@pytest.mark.asyncio(loop_scope="session")
async def test_set_jobs_found(db_session):
    run = Run(kind="scrape", correlation_id=str(uuid.uuid4()), status="succeeded")
    db_session.add(run)
    await db_session.flush()
    repo = RunsRepository(db_session)
    await repo.set_jobs_found(run.id, 42)
    await db_session.refresh(run)
    assert run.jobs_found == 42
