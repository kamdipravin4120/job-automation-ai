from __future__ import annotations

import logging
import unittest
from pathlib import Path

from src.scraper.base import BaseJobScraper
from src.utils.config import ScraperSourceConfig


class FakeLocator:
    def __init__(
        self,
        *,
        exists: bool = True,
        text: str = "",
        attributes: dict[str, str] | None = None,
    ) -> None:
        self.exists = exists
        self.text = text
        self.attributes = attributes or {}

    @property
    def first(self) -> "FakeLocator":
        return self

    def count(self) -> int:
        return 1 if self.exists else 0

    def inner_text(self) -> str:
        return self.text

    def text_content(self) -> str:
        return self.text

    def get_attribute(self, name: str) -> str | None:
        return self.attributes.get(name)


class FakeScope:
    def __init__(self, selectors: dict[str, FakeLocator | Exception]) -> None:
        self.selectors = selectors

    def locator(self, selector: str):
        value = self.selectors.get(selector, FakeLocator(exists=False))
        if isinstance(value, Exception):
            raise value
        return value


class DummyScraper(BaseJobScraper):
    def scrape(self, queries):
        return []


def build_scraper() -> DummyScraper:
    return DummyScraper(
        site_name="dummy",
        config=ScraperSourceConfig(
            storage_state_path="state.json",
            search_url_template="https://example.com?q={keywords}&location={location}",
        ),
        config_dir=Path("."),
        logger=logging.getLogger("test_scraper"),
    )


class ScraperFallbackTests(unittest.TestCase):
    def test_selector_fallback_tries_candidates_in_order(self) -> None:
        scraper = build_scraper()
        scope = FakeScope(
            {
                "broken": RuntimeError("bad selector"),
                "empty": FakeLocator(exists=False),
                "working": FakeLocator(
                    text="Primary Text",
                    attributes={"href": "https://example.com"},
                ),
            }
        )

        self.assertEqual(
            scraper._safe_text(scope, ["broken", "empty", "working"]),
            "Primary Text",
        )
        self.assertEqual(
            scraper._safe_attribute(scope, ["broken", "working"], "href"),
            "https://example.com",
        )
        self.assertEqual(scraper._locator_count(scope, ["broken", "empty", "working"]), 1)


if __name__ == "__main__":
    unittest.main()
