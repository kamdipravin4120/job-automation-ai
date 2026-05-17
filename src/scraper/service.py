from __future__ import annotations

import logging
from pathlib import Path

from src.models import JobPosting
from src.scraper.linkedin import LinkedInScraper
from src.scraper.naukri import NaukriScraper
from src.scraper.indeed import IndeedScraper
from src.scraper.glassdoor import GlassdoorScraper
from src.utils.config import AppConfig


class ScraperService:
    def __init__(self, config: AppConfig, config_dir: Path, logger: logging.Logger) -> None:
        self.config = config
        self.config_dir = config_dir
        self.logger = getattr(logger, 'getChild', lambda _: logger)("scraper")
        
        # Scraper Registry
        self._scraper_map = {
            "linkedin": LinkedInScraper,
            "naukri": NaukriScraper,
            "indeed": IndeedScraper,
            "glassdoor": GlassdoorScraper
        }

    def scrape(
        self,
        queries: list | None = None,
        sources: list[str] | None = None,
    ) -> list[JobPosting]:
        effective_queries = queries if queries is not None else self.config.search_queries
        jobs: list[JobPosting] = []

        for source_id, scraper_class in self._scraper_map.items():
            if sources is not None and source_id not in sources:
                continue
            source_config = getattr(self.config.scraper, source_id, None)

            if source_config and source_config.enabled:
                try:
                    self.logger.info("Starting %s scrape...", source_id.capitalize())
                    scraper = scraper_class(source_config, self.config_dir, self.logger)
                    scraped = scraper.scrape(effective_queries)
                    jobs.extend(scraped)
                    self.logger.info("Finished %s scrape. Found %s jobs.", source_id.capitalize(), len(scraped))
                except Exception as exc:
                    self.logger.error("%s scraper failed: %s", source_id.capitalize(), exc, exc_info=True)

        # Unified Deduplication logic
        deduped: dict[str, JobPosting] = {}
        for job in jobs:
            # We use the URL as the primary key for deduplication across platforms
            # If URL is missing, we fallback to a composite source/ID key
            key = job.url or f"{job.source}:{job.job_id}"
            deduped[key] = job
            
        results = list(deduped.values())
        self.logger.info("Total unified opportunities identified: %s", len(results))
        return results
