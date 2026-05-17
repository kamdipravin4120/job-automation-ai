from __future__ import annotations

from pathlib import Path

from src.models import JobPosting
from src.scraper.base import BaseJobScraper
from src.utils.browser import browser_session, human_delay, prompt_for_login
from src.utils.config import ScraperSourceConfig, SearchQueryConfig
from src.utils.files import resolve_path


class IndeedScraper(BaseJobScraper):
    def __init__(self, config: ScraperSourceConfig, config_dir: Path, logger) -> None:
        super().__init__(
            site_name="indeed",
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
            # Indeed often works well in anonymous mode, but storage state is used if provided
            for query in queries:
                search_url = self.build_search_url(query)
                self.logger.info("Indeed scrape started for %s", query.slug)
                
                try:
                    page.goto(search_url, wait_until="domcontentloaded")
                    human_delay(page, 1500, 3000)
                    
                    # Handle possible cookie banner
                    if self.selectors.get("cookie_banner"):
                        try:
                            page.click(self.selectors["cookie_banner"], timeout=5000)
                        except: pass

                    cards = self._find_cards(page, self.selectors["job_cards"])
                    card_count = min(cards.count(), self.config.max_jobs_per_query)
                    self.logger.info("Indeed found %d cards for query %s", cards.count(), query.slug)

                    for index in range(card_count):
                        card = cards.nth(index)
                        try:
                            card.scroll_into_view_if_needed()
                            human_delay(page, 500, 1000)
                            card.click()
                            human_delay(page, 1000, 2000)

                            # Detail View extraction
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
                            description = self._safe_text(
                                page,
                                self.selectors.get("detail_description"),
                            )
                            
                            # Indeed URLs can be complex; we use the current page URL or a data attribute
                            url = page.url if "jk=" in page.url else self._safe_attribute(card, "a[data-jk]", "href") or page.url

                            if not title or not company:
                                continue

                            jobs.append(
                                JobPosting(
                                    source="indeed",
                                    job_id=self.build_job_id("indeed", url, title, company),
                                    title=title,
                                    company=company,
                                    location=location,
                                    description=description,
                                    url=url,
                                    search_query=query.slug,
                                    metadata={"source": "Indeed Intelligence"},
                                )
                            )
                        except Exception as exc:
                            self.logger.warning("Indeed card parse failed at index %d: %s", index, exc)
                except Exception as e:
                    self.logger.error("Indeed search failed for query %s: %s", query.slug, e)
        
        return jobs
