from __future__ import annotations

from pathlib import Path

from src.tasks.celery_app import app


@app.task(name="auth_tasks.relogin_platform", queue="browser", bind=True, max_retries=0)
def relogin_platform(self, *, platform: str, email: str, password: str) -> dict:
    """Run a headless Playwright session to log in to platform and save session state."""
    from src.observability.logging import get_logger
    log = get_logger("tasks.relogin")

    state_file = Path(f"artifacts/browser/{platform}_state.json")
    state_file.parent.mkdir(parents=True, exist_ok=True)

    if platform == "linkedin":
        _login_linkedin(email=email, password=password, state_path=state_file, log=log)
    elif platform == "naukri":
        _login_naukri(email=email, password=password, state_path=state_file, log=log)
    else:
        raise ValueError(f"Unknown platform: {platform}")

    log.info("relogin.done platform=%s", platform)
    return {"ok": True, "platform": platform}


def _login_linkedin(*, email: str, password: str, state_path: Path, log) -> None:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        log.info("linkedin.login email=%s", email)
        page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        page.fill("#username", email)
        page.fill("#password", password)
        page.click('[type="submit"]')
        page.wait_for_load_state("networkidle", timeout=15000)
        ctx.storage_state(path=str(state_path))
        browser.close()


def _login_naukri(*, email: str, password: str, state_path: Path, log) -> None:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        log.info("naukri.login email=%s", email)
        page.goto("https://www.naukri.com/nlogin/login", wait_until="domcontentloaded")
        page.fill("#usernameField", email)
        page.fill("#passwordField", password)
        page.click('[type="submit"]')
        page.wait_for_load_state("networkidle", timeout=15000)
        ctx.storage_state(path=str(state_path))
        browser.close()
