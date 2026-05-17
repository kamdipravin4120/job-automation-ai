import uuid
import pytest
import pytest_asyncio


# ── AuditLog ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_audit_log_append_and_list(db_session):
    from src.data.repositories.audit_logs import AuditLogRepository
    repo = AuditLogRepository(db_session)
    entry = await repo.append(actor="device-1", action="config.update", target="config.yaml")
    assert entry.id is not None

    items, total = await repo.list_paginated(page=1, per_page=10)
    assert total >= 1
    assert any(e.action == "config.update" for e in items)


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_log_filter_by_actor(db_session):
    from src.data.repositories.audit_logs import AuditLogRepository
    repo = AuditLogRepository(db_session)
    await repo.append(actor="unique-actor-xyz", action="test.action", target="t")
    items, total = await repo.list_paginated(actor="unique-actor-xyz")
    assert total >= 1
    assert all(e.actor == "unique-actor-xyz" for e in items)


# ── Integration ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_integrations_upsert_and_list(db_session):
    from src.data.repositories.integrations import IntegrationsRepository
    repo = IntegrationsRepository(db_session)

    row = await repo.upsert(provider="test_gmail", status="connected")
    assert row.provider == "test_gmail"

    all_rows = await repo.list_all()
    assert any(r.provider == "test_gmail" for r in all_rows)


@pytest.mark.asyncio(loop_scope="session")
async def test_integrations_upsert_updates_existing(db_session):
    from src.data.repositories.integrations import IntegrationsRepository
    repo = IntegrationsRepository(db_session)
    await repo.upsert(provider="test_prov", status="connected")
    updated = await repo.upsert(provider="test_prov", status="error", last_error="token expired")
    assert updated.status == "error"
    assert updated.last_error == "token expired"


# ── SelectorOverride ──────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_selector_overrides_list_pending(db_session):
    from src.data.repositories.selector_overrides import SelectorOverridesRepository
    from src.data.models.selector_override import SelectorOverride
    repo = SelectorOverridesRepository(db_session)

    pending = SelectorOverride(
        source="linkedin",
        key_path="scraping.linkedin.job_card",
        selector=".new-selector",
        proposed_by="heal",
        status="pending",
    )
    db_session.add(pending)
    await db_session.flush()

    rows = await repo.list_pending()
    assert any(r.id == pending.id for r in rows)


@pytest.mark.asyncio(loop_scope="session")
async def test_selector_override_approve(db_session):
    from src.data.repositories.selector_overrides import SelectorOverridesRepository
    from src.data.models.selector_override import SelectorOverride
    repo = SelectorOverridesRepository(db_session)

    row = SelectorOverride(
        source="naukri",
        key_path="scraping.naukri.title",
        selector=".job-title",
        proposed_by="heal",
        status="pending",
    )
    db_session.add(row)
    await db_session.flush()

    updated = await repo.approve(row.id)
    assert updated is not None
    assert updated.status == "approved"


@pytest.mark.asyncio(loop_scope="session")
async def test_selector_override_reject(db_session):
    from src.data.repositories.selector_overrides import SelectorOverridesRepository
    from src.data.models.selector_override import SelectorOverride
    repo = SelectorOverridesRepository(db_session)

    row = SelectorOverride(
        source="linkedin",
        key_path="scraping.linkedin.company",
        selector=".company-name",
        proposed_by="operator",
        status="pending",
    )
    db_session.add(row)
    await db_session.flush()

    updated = await repo.reject(row.id)
    assert updated is not None
    assert updated.status == "rejected"


# ── ConfigVersion ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_config_version_create_and_list(db_session):
    from src.data.repositories.config_versions import ConfigVersionRepository
    repo = ConfigVersionRepository(db_session)

    ver = await repo.create(actor="device-abc", diff_patch="--- a/config.yaml\n+++ b/config.yaml\n")
    assert ver.id is not None

    recent = await repo.list_recent(limit=5)
    assert any(v.id == ver.id for v in recent)
