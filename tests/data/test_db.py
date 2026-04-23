import pytest


@pytest.mark.asyncio
async def test_engine_connects(db_session):
    from sqlalchemy import text

    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1
