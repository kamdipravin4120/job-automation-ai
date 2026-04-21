from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from src.models import ApplicationRecord
from src.tracking.repository import TrackingRepository
from src.utils.files import ensure_parent_dir

FIELDNAMES = [
    "source",
    "job_id",
    "job_title",
    "company",
    "location",
    "job_url",
    "match_score",
    "matched_skills",
    "status",
    "search_query",
    "resume_docx_path",
    "resume_text_path",
    "cover_letter_path",
    "recruiter_pitch_path",
    "notes",
    "applied_at",
    "last_updated_at",
]


class CsvTrackingRepository(TrackingRepository):
    def __init__(self, path: Path) -> None:
        self.path = path
        ensure_parent_dir(self.path)

    def upsert(self, record: ApplicationRecord) -> None:
        existing = {(item.source, item.job_id): item for item in self.list_records()}
        existing[(record.source, record.job_id)] = record
        rows = [self._serialize(item) for item in existing.values()]

        with self.path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)

    def list_records(self) -> list[ApplicationRecord]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return [self._deserialize(row) for row in reader]

    def _serialize(self, record: ApplicationRecord) -> dict[str, str]:
        payload = record.model_dump()
        payload["matched_skills"] = json.dumps(record.matched_skills)
        payload["applied_at"] = record.applied_at.isoformat() if record.applied_at else ""
        payload["last_updated_at"] = record.last_updated_at.isoformat()
        return payload

    def _deserialize(self, row: dict[str, str]) -> ApplicationRecord:
        return ApplicationRecord(
            source=row["source"],
            job_id=row["job_id"],
            job_title=row["job_title"],
            company=row["company"],
            location=row["location"],
            job_url=row["job_url"],
            match_score=float(row["match_score"] or 0.0),
            matched_skills=json.loads(row["matched_skills"] or "[]"),
            status=row["status"],
            search_query=row.get("search_query", ""),
            resume_docx_path=row.get("resume_docx_path") or None,
            resume_text_path=row.get("resume_text_path") or None,
            cover_letter_path=row.get("cover_letter_path") or None,
            recruiter_pitch_path=row.get("recruiter_pitch_path") or None,
            notes=row.get("notes", ""),
            applied_at=datetime.fromisoformat(row["applied_at"]) if row.get("applied_at") else None,
            last_updated_at=datetime.fromisoformat(row["last_updated_at"]),
        )

