from __future__ import annotations

from pathlib import Path

from src.models import JobPosting
from src.scraper.base import BaseJobScraper
from src.utils.browser import browser_session, human_delay, prompt_for_login
from src.utils.config import ScraperSourceConfig, SearchQueryConfig
from src.utils.files import resolve_path


class NaukriScraper(BaseJobScraper):
    def __init__(self, config: ScraperSourceConfig, config_dir: Path, logger) -> None:
        super().__init__(
            site_name="naukri",
            config=config,
            config_dir=config_dir,
            logger=logger,
        )
        self.selectors = config.selectors

    def build_search_url(self, query: SearchQueryConfig) -> str:
        keywords = query.keywords.strip().lower().replace(" ", "-")
        location = query.location.strip().lower().replace(" ", "-")
        return self.config.search_url_template.format(keywords=keywords, location=location)

    def scrape(self, queries: list[SearchQueryConfig]) -> list[JobPosting]:
        storage_state = resolve_path(self.config_dir, self.config.storage_state_path)
        jobs: list[JobPosting] = []

        with browser_session(
            headless=self.config.headless,
            timeout_ms=self.config.timeout_ms,
            storage_state_path=storage_state,
        ) as (context, page):
            prompt_for_login(
                page,
                landing_url="https://www.naukri.com/",
                login_check_selector=self.selectors.get("login_check"),
            )

            for query in queries:
                search_url = self.build_search_url(query)
                self.logger.info("Naukri scrape started for %s", query.slug)
                page.goto(search_url, wait_until="domcontentloaded")
                self._prime_results(page)

                cards = self._find_cards(page, self.selectors["job_cards"])
                card_count = min(cards.count(), self.config.max_jobs_per_query)

                for index in range(card_count):
                    card = cards.nth(index)
                    try:
                        title = self._safe_text(card, self.selectors.get("card_title"))
                        company = self._safe_text(card, self.selectors.get("card_company"))
                        location = self._safe_text(card, self.selectors.get("card_location"))
                        url = self._safe_attribute(card, self.selectors.get("card_link"), "href")
                        description = ""
                        detail_title = ""
                        detail_company = ""
                        detail_location = ""

                        if url:
                            detail_page = context.new_page()
                            detail_page.set_default_timeout(self.config.timeout_ms)
                            detail_page.goto(url, wait_until="domcontentloaded")
                            human_delay(detail_page, 800, 1200)
                            detail_title = self._safe_text(
                                detail_page,
                                self.selectors.get("detail_title"),
                            )
                            detail_company = self._safe_text(
                                detail_page,
                                self.selectors.get("detail_company"),
                            )
                            detail_location = self._safe_text(
                                detail_page,
                                self.selectors.get("detail_location"),
                            )
                            description = self._safe_text(
                                detail_page,
                                self.selectors.get("detail_description"),
                            )
                            detail_page.close()

                        title = self._first_non_empty(detail_title, title)
                        company = self._first_non_empty(detail_company, company)
                        location = self._first_non_empty(detail_location, location)
                        if not title or not company or not url:
                            continue

                        jobs.append(
                            JobPosting(
                                source="naukri",
                                job_id=self.build_job_id("naukri", url, title, company),
                                title=title,
                                company=company,
                                location=location,
                                description=description,
                                url=url,
                                search_query=query.slug,
                            )
                        )
                    except Exception as exc:
                        self.logger.warning("Naukri card parse failed: %s", exc)
        return jobs

    def _prime_results(self, page) -> None:
        for _ in range(4):
            page.mouse.wheel(0, 2000)
            human_delay(page, 400, 900)
