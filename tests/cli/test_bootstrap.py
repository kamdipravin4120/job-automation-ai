import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_bootstrap_stores_secret_in_redis(redis_container):
    import redis.asyncio as aioredis

    redis_url = (
        f"redis://{redis_container.get_container_host_ip()}"
        f":{redis_container.get_exposed_port(6379)}/0"
    )
    from src.cli.bootstrap import run as bootstrap_run

    secret = bootstrap_run(redis_url=redis_url, print_qr=False)
    assert secret is not None and len(secret) == 64  # 32 bytes hex

    r = aioredis.from_url(redis_url)
    val = await r.get(f"bootstrap:{secret}")
    await r.aclose()
    assert val is not None
    ttl_remaining = await r.ttl(f"bootstrap:{secret}")
    assert ttl_remaining > 0
