from __future__ import annotations

import logging
from pathlib import Path

from src.models import ApplicationRecord
from src.utils.browser import browser_session, human_delay, prompt_for_login
from src.utils.config import ApplyConfig
from src.utils.files import resolve_path


class LinkedInEasyApplyBot:
    def __init__(self, config: ApplyConfig, config_dir: Path, logger: logging.Logger) -> None:
        self.config = config
        self.config_dir = config_dir
        self.logger = logger.getChild("linkedin_easy_apply")

    def apply(self, records: list[ApplicationRecord], limit: int | None = None) -> list[ApplicationRecord]:
        if not records:
            return []

        storage_state_path = resolve_path(self.config_dir, self.config.storage_state_path)
        results: list[ApplicationRecord] = []
        max_records = limit or self.config.max_applications_per_run

        with browser_session(
            headless=self.config.headless,
            timeout_ms=self.config.timeout_ms,
            storage_state_path=storage_state_path,
        ) as (context, page):
            prompt_for_login(
                page,
                landing_url="https://www.linkedin.com/feed/",
                login_check_selector=self.config.login_check_selector,
            )
            
            # Double-check: ensure the user profile photo is genuinely visible
            is_logged_in = False
            for selector in (self.config.login_check_selector or ["img.global-nav__me-photo"]):
                if page.locator(selector).first.is_visible():
                    is_logged_in = True
                    break
            
            if not is_logged_in:
                self.logger.warning("Session appears expired. Requesting manual re-authentication.")
                prompt_for_login(page, landing_url="https://www.linkedin.com/feed/", login_check_selector="img.global-nav__me-photo")

            for record in records[:max_records]:
                page = context.new_page()
                page.set_default_timeout(self.config.timeout_ms)
                try:
                    updated = self._apply_single(page, record)
                    results.append(updated)
                except Exception as exc:
                    record.status = "error"
                    record.notes = f"Application failed: {exc}"
                    results.append(record)
                    self.logger.exception("Easy Apply failed for %s", record.job_id)
                finally:
                    page.close()
        return results

    def _apply_single(self, page, record: ApplicationRecord) -> ApplicationRecord:
        if not record.resume_docx_path:
            record.status = "error"
            record.notes = "Resume DOCX path missing."
            return record

        target_url = record.job_url
        if target_url.startswith("/"):
            target_url = f"https://www.linkedin.com{target_url}"

        self.logger.info("Opening LinkedIn application for %s", target_url)
        page.goto(target_url, wait_until="domcontentloaded")
        human_delay(page, self.config.human_delay_min_ms, self.config.human_delay_max_ms)

        # Robust search for Easy Apply button including iframes
        easy_apply_button = page.locator(self.config.easy_apply_button_selector).first
        if not easy_apply_button.is_visible():
            found_in_frame = False
            for frame in page.frames:
                button = frame.locator(self.config.easy_apply_button_selector).first
                if button.is_visible():
                    easy_apply_button = button
                    found_in_frame = True
                    self.logger.info("Found Easy Apply button in iframe: %s", frame.name)
                    break
            
            if not found_in_frame:
                record.status = "manual_review_required"
                record.notes = "Easy Apply button not found or hidden."
                debug_path = resolve_path(self.config_dir, Path(f"artifacts/debug_apply_{record.job_id[:20]}.png"))
                page.screenshot(path=str(debug_path))
                self.logger.warning("Easy Apply button missing for %s. Screenshot saved: %s", record.job_id, debug_path)
                return record
        
        self.logger.info("Clicking Easy Apply button (forced)...")
        easy_apply_button.click(force=True)
        # Give modal a moment to animate
        page.wait_for_timeout(2000)
        
        # Verify modal is present
        if page.locator(".jobs-easy-apply-modal").count() == 0 and page.locator(".jobs-easy-apply-content").count() == 0:
            self.logger.warning("Application modal did not appear after click.")
            # Fallback: JavaScript click
            page.evaluate(f"document.querySelector(\"{self.config.easy_apply_button_selector}\").click()")
            page.wait_for_timeout(2000)

        human_delay(page, self.config.human_delay_min_ms, self.config.human_delay_max_ms)

        self._upload_resume_if_present(page, record.resume_docx_path)

        for _ in range(8):
            human_delay(page, self.config.human_delay_min_ms, self.config.human_delay_max_ms)

            submit_button = page.locator(self.config.submit_button_selector).first
            if submit_button.is_visible():
                self.logger.info("Found Submit button.")
                if self.config.manual_review_required:
                    decision = input(
                        f"Submit application for '{record.job_title}' at '{record.company}'? [y/N]: "
                    ).strip().lower()
                    if decision != "y":
                        record.status = "manual_review_required"
                        record.notes = "Submission paused for manual review."
                        self._dismiss_dialog(page)
                        return record

                submit_button.click()
                human_delay(page, self.config.human_delay_min_ms, self.config.human_delay_max_ms)
                self._dismiss_dialog(page)
                record.status = "applied"
                record.notes = "Application submitted through LinkedIn Easy Apply."
                return record

            review_button = page.locator(self.config.review_button_selector).first
            if review_button.is_visible():
                self.logger.info("Found Review button. Clicking...")
                review_button.click()
                continue

            next_button = page.locator(self.config.next_button_selector).first
            if next_button.is_visible():
                if not next_button.is_enabled():
                    self.logger.warning("Next button found but disabled. Mandatory questions might be missing.")
                    record.status = "manual_review_required"
                    record.notes = "Form blocked: Next button disabled (mandatory questions?)"
                    return record
                
                self.logger.info("Found Next button. Clicking...")
                next_button.click()
                self._upload_resume_if_present(page, record.resume_docx_path)
                continue

            self.logger.warning("No progression buttons (Next/Review/Submit) found on current step.")
            record.status = "manual_review_required"
            record.notes = "Unhandled form state encountered (no buttons found)."
            debug_path = resolve_path(self.config_dir, Path(f"artifacts/debug_form_stuck_{record.job_id[:20]}.png"))
            page.screenshot(path=str(debug_path))
            self.logger.warning("Form progression failed for %s. Screenshot saved: %s", record.job_id, debug_path)
            return record

        record.status = "manual_review_required"
        record.notes = "Reached multi-step safety limit before submission."
        return record

    def _upload_resume_if_present(self, page, resume_docx_path: str) -> None:
        file_input = page.locator(self.config.resume_file_input_selector)
        if file_input.count() == 0:
            return
        file_input.first.set_input_files(resume_docx_path)
        page.wait_for_timeout(self.config.upload_wait_ms)

    def _dismiss_dialog(self, page) -> None:
        dismiss_button = page.locator(self.config.dismiss_button_selector)
        if dismiss_button.count() > 0:
            dismiss_button.first.click()
