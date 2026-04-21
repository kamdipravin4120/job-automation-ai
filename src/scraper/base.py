from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import quote_plus

from src.models import JobPosting
from src.utils.config import ScraperSourceConfig, SearchQueryConfig, SelectorConfigValue
from src.utils.text import normalize_text, slugify


class BaseJobScraper(ABC):
    def __init__(
        self,
        *,
        site_name: str,
        config: ScraperSourceConfig,
        config_dir: Path,
        logger: logging.Logger,
    ) -> None:
        self.site_name = site_name
        self.config = config
        self.config_dir = config_dir
        self.logger = logger.getChild(f"scraper.{site_name}")

    @abstractmethod
    def scrape(self, queries: list[SearchQueryConfig]) -> list[JobPosting]:
        raise NotImplementedError

    def build_search_url(self, query: SearchQueryConfig) -> str:
        return self.config.search_url_template.format(
            keywords=quote_plus(query.keywords),
            location=quote_plus(query.location),
        )

    @staticmethod
    def build_job_id(source: str, url: str, title: str, company: str) -> str:
        base = url or f"{title}-{company}"
        return f"{source}-{slugify(base)}"

    @staticmethod
    def text_or_default(value: str | None, default: str = "") -> str:
        return normalize_text(value or default)

    @staticmethod
    def _first_non_empty(*values: str) -> str:
        for value in values:
            normalized = normalize_text(value)
            if normalized:
                return normalized
        return ""

    @staticmethod
    def _normalize_selector_values(
        selector: SelectorConfigValue | None,
    ) -> list[str]:
        if selector is None:
            return []
        if isinstance(selector, str):
            return [selector]
        return [item for item in selector if item]

    def _find_cards(self, scope, selector: SelectorConfigValue | None):
        candidates = self._normalize_selector_values(selector)
        for candidate in candidates:
            try:
                locator = scope.locator(candidate)
                if locator.count() > 0:
                    return locator
            except Exception as exc:
                self.logger.debug("Card selector candidate failed for %s: %s", candidate, exc)
        
        # If none found, return the first one (which will have count 0) or a dummy
        return scope.locator(candidates[0] if candidates else "NOT_FOUND")

    def _first_locator(self, scope, selector: SelectorConfigValue | None):
        for candidate in self._normalize_selector_values(selector):
            try:
                locator = scope.locator(candidate)
                if locator.count() > 0:
                    return locator.first
            except Exception as exc:
                self.logger.debug("Selector candidate failed for %s: %s", candidate, exc)
        return None

    def _safe_text(
        self,
        scope,
        selector: SelectorConfigValue | None,
        default: str = "",
    ) -> str:
        locator = self._first_locator(scope, selector)
        if locator is None:
            return default
        try:
            return self.text_or_default(locator.inner_text(), default=default)
        except Exception:
            try:
                return self.text_or_default(locator.text_content(), default=default)
            except Exception:
                return default

    def _safe_attribute(
        self,
        scope,
        selector: SelectorConfigValue | None,
        attribute_name: str,
        default: str = "",
    ) -> str:
        locator = self._first_locator(scope, selector)
        if locator is None:
            return default
        try:
            return locator.get_attribute(attribute_name) or default
        except Exception:
            return default

    def _locator_count(self, scope, selector: SelectorConfigValue | None) -> int:
        for candidate in self._normalize_selector_values(selector):
            try:
                locator = scope.locator(candidate)
                count = locator.count()
                if count > 0:
                    return count
            except Exception as exc:
                self.logger.debug("Selector count failed for %s: %s", candidate, exc)
        return 0
