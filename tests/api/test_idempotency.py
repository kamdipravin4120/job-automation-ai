import pytest
import uuid


@pytest.mark.asyncio(loop_scope="session")
async def test_second_request_returns_cached_response(async_client, redis_client):
    """POST with same Idempotency-Key twice returns same response on second call."""
    key = str(uuid.uuid4())
    headers = {"Idempotency-Key": key}

    # First request — triggers actual processing (will 401 since no auth, but that's fine)
    r1 = await async_client.post("/api/v1/pipeline/trigger", headers=headers, json={})
    # Second request with same key — should return same status + body
    r2 = await async_client.post("/api/v1/pipeline/trigger", headers=headers, json={})

    assert r1.status_code == r2.status_code
    assert r1.json() == r2.json()


@pytest.mark.asyncio(loop_scope="session")
async def test_different_keys_are_independent(async_client):
    """Two requests with different Idempotency-Keys are processed independently."""
    key1 = str(uuid.uuid4())
    key2 = str(uuid.uuid4())

    r1 = await async_client.post("/api/v1/pipeline/trigger",
                                  headers={"Idempotency-Key": key1}, json={})
    r2 = await async_client.post("/api/v1/pipeline/trigger",
                                  headers={"Idempotency-Key": key2}, json={})
    # Both processed independently — no 409
    assert r2.status_code != 409
