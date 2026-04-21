from __future__ import annotations

from pathlib import Path

from src.models import JobPosting
from src.scraper.base import BaseJobScraper
from src.utils.browser import browser_session, human_delay
from src.utils.config import ScraperSourceConfig, SearchQueryConfig
from src.utils.files import resolve_path


class GlassdoorScraper(BaseJobScraper):
    def __init__(self, config: ScraperSourceConfig, config_dir: Path, logger) -> None:
        super().__init__(
            site_name="glassdoor",
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
            for query in queries:
                search_url = self.build_search_url(query)
                self.logger.info("Glassdoor scrape started for %s", query.slug)
                
                try:
                    page.goto(search_url, wait_until="domcontentloaded")
                    human_delay(page, 2000, 4000)
                    
                    # Handle High-Security Login Modal if it appears
                    self._bypass_modal(page)

                    cards = self._find_cards(page, self.selectors.get("job_cards", "[data-test='jobListing']"))
                    card_count = min(cards.count(), self.config.max_jobs_per_query)
                    self.logger.info("Glassdoor found %d cards for query %s", cards.count(), query.slug)

                    for index in range(card_count):
                        card = cards.nth(index)
                        try:
                            # Close modal again if it re-appears during scrolling/clicking
                            self._bypass_modal(page)
                            
                            card.scroll_into_view_if_needed()
                            human_delay(page, 500, 1000)
                            card.click()
                            human_delay(page, 1500, 2500)

                            # Handle 'Show More' if needed
                            show_more = page.locator(self.selectors.get("show_more", "[data-test='show-more']"))
                            if show_more.is_visible():
                                show_more.click()
                                human_delay(page, 500, 800)

                            # Extraction using resilient data-test attributes
                            title = self._first_non_empty(
                                self._safe_text(page, self.selectors.get("detail_title", "[data-test='job-title']")),
                                self._safe_text(card, self.selectors.get("card_title")),
                            )
                            company = self._first_non_empty(
                                self._safe_text(page, self.selectors.get("detail_company", "[data-test='job-listing-company']")),
                                self._safe_text(card, self.selectors.get("card_company")),
                            )
                            location = self._first_non_empty(
                                self._safe_text(page, self.selectors.get("detail_location", "[data-test='job-location']")),
                                self._safe_text(card, self.selectors.get("card_location")),
                            )
                            description = self._safe_text(
                                page,
                                self.selectors.get("detail_description", "[data-test='job-description']"),
                            )
                            
                            url = page.url

                            if not title or not company:
                                continue

                            jobs.append(
                                JobPosting(
                                    source="glassdoor",
                                    job_id=self.build_job_id("glassdoor", url, title, company),
                                    title=title,
                                    company=company,
                                    location=location,
                                    description=description,
                                    url=url,
                                    search_query=query.slug,
                                    metadata={"source": "Glassdoor Intelligence"},
                                )
                            )
                        except Exception as exc:
                            self.logger.warning("Glassdoor card parse failed at index %d: %s", index, exc)
                except Exception as e:
                    self.logger.error("Glassdoor search failed for query %s: %s", query.slug, e)
        
        return jobs

    def _bypass_modal(self, page) -> None:
        """Attempts to close the persistent login modal."""
        close_btn_selector = self.selectors.get("modal_close", "[data-test='modal-close-close-button']")
        try:
            close_btn = page.locator(close_btn_selector)
            if close_btn.is_visible():
                close_btn.click()
                self.logger.info("Glassdoor login modal bypassed.")
        except:
            pass
