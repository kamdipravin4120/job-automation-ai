from __future__ import annotations

import logging
import os
import unittest
from datetime import UTC, datetime

from src.models import ApplicationRecord
from src.tracking.notion_sync import NotionApplicationTrackingSync
from src.utils.config import NotionSyncConfig


class FakeNotionAPIClient:
    def __init__(self) -> None:
        self.created_payloads: list[dict] = []
        self.updated_payloads: list[dict] = []
        self.queries: int = 0

    def query_data_source(
        self,
        *,
        data_source_id: str,
        start_cursor: str | None = None,
        page_size: int = 100,
    ) -> dict:
        self.queries += 1
        return {
            "results": [
                {
                    "id": "page-existing",
                    "properties": {
                        "Job URL": {
                            "type": "url",
                            "url": "https://example.com/jobs/existing",
                        }
                    },
                }
            ],
            "has_more": False,
            "next_cursor": None,
        }

    def create_page(self, *, data_source_id: str, properties: dict) -> dict:
        self.created_payloads.append(
            {
                "data_source_id": data_source_id,
                "properties": properties,
            }
        )
        return {"id": "page-created"}

    def update_page(self, *, page_id: str, properties: dict) -> dict:
        self.updated_payloads.append({"page_id": page_id, "properties": properties})
        return {"id": page_id}


class NotionSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["TEST_NOTION_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        os.environ.pop("TEST_NOTION_API_KEY", None)

    def _build_sync_service(
        self,
        *,
        api_client: FakeNotionAPIClient | None = None,
    ) -> NotionApplicationTrackingSync:
        return NotionApplicationTrackingSync(
            NotionSyncConfig(
                enabled=True,
                api_key_env_var="TEST_NOTION_API_KEY",
                application_tracking_data_source_id="test-data-source",
                max_records_per_sync=50,
            ),
            logging.getLogger("test_notion_sync"),
            api_client=api_client,
        )

    def test_build_notion_properties_maps_local_record_fields(self) -> None:
        sync_service = self._build_sync_service()
        record = ApplicationRecord(
            source="linkedin",
            job_id="job-1",
            job_title="Senior Python Engineer",
            company="Acme",
            location="Remote",
            job_url="https://example.com/jobs/1",
            match_score=0.93218,
            matched_skills=["Python", "OpenAI"],
            status="manual_action_required",
            search_query="Senior Python Engineer::Remote",
            notes="Needs review",
            applied_at=datetime(2026, 4, 18, 8, 30, tzinfo=UTC),
        )

        properties = sync_service.build_notion_properties(record)

        self.assertEqual(
            properties["Application"]["title"][0]["text"]["content"],
            "Senior Python Engineer",
        )
        self.assertEqual(properties["Source"]["select"]["name"], "linkedin")
        self.assertEqual(
            properties["Pipeline Status"]["select"]["name"],
            "manual_review_required",
        )
        self.assertEqual(properties["Match Score"]["number"], 0.9322)
        self.assertEqual(
            properties["Matched Skills"]["rich_text"][0]["text"]["content"],
            "Python, OpenAI",
        )
        self.assertEqual(
            properties["Applied At"]["date"]["start"],
            "2026-04-18T08:30:00+00:00",
        )

    def test_sync_records_updates_existing_pages_and_creates_missing_pages(self) -> None:
        fake_client = FakeNotionAPIClient()
        sync_service = self._build_sync_service(api_client=fake_client)

        existing_record = ApplicationRecord(
            source="linkedin",
            job_id="job-existing",
            job_title="Existing Role",
            company="Acme",
            location="Remote",
            job_url="https://example.com/jobs/existing",
            status="matched",
        )
        new_record = ApplicationRecord(
            source="naukri",
            job_id="job-new",
            job_title="New Role",
            company="Beta",
            location="Bengaluru",
            job_url="https://example.com/jobs/new",
            status="scraped",
        )

        summary = sync_service.sync_records([existing_record, new_record])

        self.assertEqual(fake_client.queries, 1)
        self.assertEqual(summary.updated, 1)
        self.assertEqual(summary.created, 1)
        self.assertEqual(summary.skipped, 0)
        self.assertEqual(fake_client.updated_payloads[0]["page_id"], "page-existing")
        self.assertEqual(
            fake_client.created_payloads[0]["data_source_id"],
            "test-data-source",
        )


if __name__ == "__main__":
    unittest.main()
