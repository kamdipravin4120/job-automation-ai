from __future__ import annotations

from pathlib import Path

from src.models import JobPosting
from src.scraper.base import BaseJobScraper
from src.utils.browser import browser_session, human_delay, prompt_for_login
from src.utils.config import ScraperSourceConfig, SearchQueryConfig
from src.utils.files import resolve_path


class LinkedInScraper(BaseJobScraper):
    def __init__(self, config: ScraperSourceConfig, config_dir: Path, logger) -> None:
        super().__init__(
            site_name="linkedin",
            config=config,
            config_dir=config_dir,
            logger=logger,
        )
        self.selectors = config.selectors

    def scrape(self, queries: list[SearchQueryConfig]) -> list[JobPosting]:
        storage_state = resolve_path(self.config_dir, self.config.storage_state_path)
        jobs: list[JobPosting] = []

        with browser_session(
            headless=self.config.headless,
            timeout_ms=self.config.timeout_ms,
            storage_state_path=storage_state,
        ) as (_, page):
            prompt_for_login(
                page,
                landing_url="https://www.linkedin.com/feed/",
                login_check_selector=self.selectors.get("login_check"),
            )

            for query in queries:
                search_url = self.build_search_url(query)
                self.logger.info("LinkedIn scrape started for %s", query.slug)
                page.goto(search_url, wait_until="domcontentloaded")
                self._prime_results(page)

                cards = self._find_cards(page, self.selectors["job_cards"])
                card_count = min(cards.count(), self.config.max_jobs_per_query)

                for index in range(card_count):
                    card = cards.nth(index)
                    try:
                        card.scroll_into_view_if_needed()
                        human_delay(page, 400, 900)
                        card.click()
                        human_delay(page, 800, 1400)

                        title = self._first_non_empty(
                            self._safe_text(page, self.selectors.get("detail_title")),
                            self._safe_text(card, self.selectors.get("card_title")),
                        )
                        company = self._first_non_empty(
                            self._safe_text(page, self.selectors.get("detail_company")),
                            self._safe_text(card, self.selectors.get("card_company")),
                        )
                        location = self._first_non_empty(
                            self._safe_text(page, self.selectors.get("detail_location")),
                            self._safe_text(card, self.selectors.get("card_location")),
                        )
                        url = self._first_non_empty(
                            self._safe_attribute(card, self.selectors.get("card_link"), "href"),
                            page.url,
                        )
                        description = self._safe_text(
                            page,
                            self.selectors.get("detail_description"),
                        )
                        if not title or not company or not url:
                            continue

                        jobs.append(
                            JobPosting(
                                source="linkedin",
                                job_id=self.build_job_id("linkedin", url, title, company),
                                title=title,
                                company=company,
                                location=location,
                                description=description,
                                url=url,
                                search_query=query.slug,
                                metadata={
                                    "easy_apply_available": self._locator_count(
                                        page,
                                        self.selectors.get("easy_apply_button"),
                                    )
                                    > 0
                                },
                            )
                        )
                    except Exception as exc:
                        self.logger.warning("LinkedIn card parse failed: %s", exc)
        return jobs

    def _prime_results(self, page) -> None:
        for _ in range(4):
            page.mouse.wheel(0, 1800)
            human_delay(page, 500, 1000)
