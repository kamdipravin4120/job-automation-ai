# tests/api/test_spa.py
import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_spa_root_returns_html(async_client):
    r = await async_client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


@pytest.mark.asyncio(loop_scope="session")
async def test_spa_subroute_returns_html(async_client):
    r = await async_client.get("/dashboard")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


@pytest.mark.asyncio(loop_scope="session")
async def test_static_css_served(async_client):
    r = await async_client.get("/static/style.css")
    assert r.status_code == 200
    assert "text/css" in r.headers["content-type"]
