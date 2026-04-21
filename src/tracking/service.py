from __future__ import annotations

import logging
from pathlib import Path

from src.models import ApplicationRecord
from src.tracking.csv_repository import CsvTrackingRepository
from src.tracking.repository import TrackingRepository
from src.tracking.sqlite_repository import SqliteTrackingRepository
from src.utils.config import TrackingConfig
from src.utils.files import resolve_path


class TrackingService:
    def __init__(self, config: TrackingConfig, config_dir: Path, logger: logging.Logger) -> None:
        self.logger = logger.getChild("tracking")
        self.repository = self._build_repository(config, config_dir)

    def _build_repository(self, config: TrackingConfig, config_dir: Path) -> TrackingRepository:
        if config.mode.lower() == "csv":
            return CsvTrackingRepository(resolve_path(config_dir, config.csv_path))
        return SqliteTrackingRepository(resolve_path(config_dir, config.sqlite_path))

    def upsert_record(self, record: ApplicationRecord) -> None:
        self.repository.upsert(record)

    def list_records(self) -> list[ApplicationRecord]:
        return self.repository.list_records()

    def actionable_records(self) -> list[ApplicationRecord]:
        return [
            record
            for record in self.list_records()
            if record.resume_docx_path and record.status in {"resume_generated", "manual_review_required"}
        ]

