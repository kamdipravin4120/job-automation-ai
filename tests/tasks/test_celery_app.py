def test_celery_app_has_four_queues():
    from src.tasks.celery_app import celery_app

    queues = {q.name for q in celery_app.conf.task_queues}
    assert queues == {"scrape", "ai", "browser", "mail"}


def test_broker_url_reads_from_settings(monkeypatch):
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://test:6379/9")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://test:6379/9")
    # Settings is lru_cached, celery_app.py reads settings at module import.
    # Clearing the cache and reloading picks up the new env vars.
    import importlib

    from src import settings as settings_mod
    import src.tasks.celery_app as mod

    settings_mod.get_settings.cache_clear()
    importlib.reload(mod)
    assert mod.celery_app.conf.broker_url == "redis://test:6379/9"
