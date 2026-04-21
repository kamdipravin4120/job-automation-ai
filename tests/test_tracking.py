from __future__ import annotations

import logging
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from src.models import ApplicationRecord
from src.tracking.service import TrackingService
from src.utils.config import TrackingConfig


class TrackingServiceTests(unittest.TestCase):
    def test_tracking_service_persists_and_filters_actionable_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = TrackingService(
                TrackingConfig(mode="sqlite", sqlite_path="tracker.db"),
                Path(temp_dir),
                logging.getLogger("test_tracking"),
            )

            matched_only = ApplicationRecord(
                source="linkedin",
                job_id="job-1",
                job_title="Engineer",
                company="Acme",
                location="Remote",
                job_url="https://example.com/jobs/1",
                status="matched",
                last_updated_at=datetime.now(UTC),
            )
            resume_ready = ApplicationRecord(
                source="linkedin",
                job_id="job-2",
                job_title="Engineer II",
                company="Beta",
                location="Remote",
                job_url="https://example.com/jobs/2",
                status="resume_generated",
                resume_docx_path="/tmp/resume.docx",
                last_updated_at=datetime.now(UTC),
            )

            service.upsert_record(matched_only)
            service.upsert_record(resume_ready)

            all_records = service.list_records()
            actionable = service.actionable_records()

            self.assertEqual(len(all_records), 2)
            self.assertEqual(len(actionable), 1)
            self.assertEqual(actionable[0].job_id, "job-2")


if __name__ == "__main__":
    unittest.main()
