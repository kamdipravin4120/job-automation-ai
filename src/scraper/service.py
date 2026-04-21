from __future__ import annotations

import logging
from pathlib import Path

from src.models import JobPosting
from src.scraper.linkedin import LinkedInScraper
from src.scraper.naukri import NaukriScraper
from src.utils.config import AppConfig


class ScraperService:
    def __init__(self, config: AppConfig, config_dir: Path, logger: logging.Logger) -> None:
        self.config = config
        self.config_dir = config_dir
        self.logger = logger.getChild("scraper")

    def scrape(self) -> list[JobPosting]:
        jobs: list[JobPosting] = []

        # LinkedIn Scraping
        if self.config.scraper.linkedin.enabled:
            try:
                self.logger.info("Starting LinkedIn scrape...")
                scraped = LinkedInScraper(
                    self.config.scraper.linkedin, self.config_dir, self.logger
                ).scrape(self.config.search_queries)
                jobs.extend(scraped)
                self.logger.info("Finished LinkedIn scrape. Found %s jobs.", len(scraped))
            except Exception as exc:
                self.logger.error("LinkedIn scraper failed: %s", exc, exc_info=True)

        # Naukri Scraping
        if self.config.scraper.naukri.enabled:
            try:
                self.logger.info("Starting Naukri scrape...")
                scraped = NaukriScraper(
                    self.config.scraper.naukri, self.config_dir, self.logger
                ).scrape(self.config.search_queries)
                jobs.extend(scraped)
                self.logger.info("Finished Naukri scrape. Found %s jobs.", len(scraped))
            except Exception as exc:
                self.logger.error("Naukri scraper failed: %s", exc, exc_info=True)

        deduped: dict[str, JobPosting] = {}
        for job in jobs:
            key = job.url or f"{job.source}:{job.job_id}"
            deduped[key] = job
        results = list(deduped.values())
        self.logger.info("Total deduped jobs scraped: %s", len(results))
        return results

