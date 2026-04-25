import pytest
import uuid
from datetime import UTC, datetime


@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_get_device(db_session):
    from src.data.repositories.devices import DevicesRepository

    repo = DevicesRepository(db_session)
    device = await repo.create(
        public_key="-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
        pairing_ip="127.0.0.1",
    )
    assert device.id is not None
    assert device.revoked_at is None

    fetched = await repo.get(device.id)
    assert fetched is not None
    assert fetched.public_key == device.public_key


@pytest.mark.asyncio(loop_scope="session")
async def test_touch_updates_last_seen(db_session):
    from src.data.repositories.devices import DevicesRepository

    repo = DevicesRepository(db_session)
    device = await repo.create(public_key=f"pk-touch-test-{uuid.uuid4()}", pairing_ip=None)
    await repo.touch(device.id, ip="10.0.0.1", user_agent="TestAgent/1")
    await db_session.refresh(device)
    assert device.last_ip == "10.0.0.1"
    assert device.last_user_agent == "TestAgent/1"
    assert device.last_seen_at is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_revoke_sets_revoked_at(db_session):
    from src.data.repositories.devices import DevicesRepository

    repo = DevicesRepository(db_session)
    device = await repo.create(public_key=f"pk-revoke-test-{uuid.uuid4()}", pairing_ip=None)
    assert device.revoked_at is None
    await repo.revoke(device.id)
    await db_session.refresh(device)
    assert device.revoked_at is not None
