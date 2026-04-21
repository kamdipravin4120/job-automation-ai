from __future__ import annotations

import random
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, sync_playwright

from src.utils.files import ensure_parent_dir


@contextmanager
def browser_session(
    *,
    headless: bool,
    timeout_ms: int,
    storage_state_path: Path | None = None,
) -> Iterator[tuple[BrowserContext, Page]]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context_kwargs: dict[str, str] = {}
        if storage_state_path and storage_state_path.exists():
            context_kwargs["storage_state"] = str(storage_state_path)

        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            yield context, page
        finally:
            if storage_state_path:
                ensure_parent_dir(storage_state_path)
                try:
                    context.storage_state(path=str(storage_state_path))
                except Exception as exc:
                    # Catch cases where browser is closed manually
                    print(f"Warning: Could not save storage state to {storage_state_path}: {exc}")
            try:
                context.close()
                browser.close()
            except Exception:
                pass


def human_delay(page: Page, min_ms: int, max_ms: int) -> None:
    page.wait_for_timeout(random.randint(min_ms, max_ms))


def prompt_for_login(
    page: Page,
    *,
    landing_url: str,
    login_check_selector: str | list[str] | None,
) -> None:
    page.goto(landing_url, wait_until="domcontentloaded")
    
    selectors = (
        [login_check_selector]
        if isinstance(login_check_selector, str)
        else (login_check_selector or [])
    )
    for selector in selectors:
        if selector and page.locator(selector).count() > 0:
            return

    print(f"Login required in the opened browser for: {landing_url}")
    input("Complete the login flow, then press Enter to continue...")
    page.goto(landing_url, wait_until="domcontentloaded")

