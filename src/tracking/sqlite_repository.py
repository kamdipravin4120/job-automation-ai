from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from src.models import ApplicationRecord
from src.tracking.repository import TrackingRepository
from src.utils.files import ensure_parent_dir


class SqliteTrackingRepository(TrackingRepository):
    def __init__(self, path: Path) -> None:
        self.path = path
        ensure_parent_dir(self.path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_applications (
                    source TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    job_title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT NOT NULL,
                    job_url TEXT NOT NULL,
                    match_score REAL NOT NULL,
                    matched_skills TEXT NOT NULL,
                    status TEXT NOT NULL,
                    search_query TEXT NOT NULL,
                    resume_docx_path TEXT,
                    resume_text_path TEXT,
                    cover_letter_path TEXT,
                    recruiter_pitch_path TEXT,
                    notes TEXT NOT NULL,
                    applied_at TEXT,
                    last_updated_at TEXT NOT NULL,
                    PRIMARY KEY (source, job_id)
                )
                """
            )

    def upsert(self, record: ApplicationRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO job_applications (
                    source, job_id, job_title, company, location, job_url, match_score,
                    matched_skills, status, search_query, resume_docx_path, resume_text_path,
                    cover_letter_path, recruiter_pitch_path, notes, applied_at, last_updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, job_id) DO UPDATE SET
                    job_title=excluded.job_title,
                    company=excluded.company,
                    location=excluded.location,
                    job_url=excluded.job_url,
                    match_score=excluded.match_score,
                    matched_skills=excluded.matched_skills,
                    status=excluded.status,
                    search_query=excluded.search_query,
                    resume_docx_path=excluded.resume_docx_path,
                    resume_text_path=excluded.resume_text_path,
                    cover_letter_path=excluded.cover_letter_path,
                    recruiter_pitch_path=excluded.recruiter_pitch_path,
                    notes=excluded.notes,
                    applied_at=excluded.applied_at,
                    last_updated_at=excluded.last_updated_at
                """,
                (
                    record.source,
                    record.job_id,
                    record.job_title,
                    record.company,
                    record.location,
                    record.job_url,
                    record.match_score,
                    json.dumps(record.matched_skills),
                    record.status,
                    record.search_query,
                    record.resume_docx_path,
                    record.resume_text_path,
                    record.cover_letter_path,
                    record.recruiter_pitch_path,
                    record.notes,
                    record.applied_at.isoformat() if record.applied_at else None,
                    record.last_updated_at.isoformat(),
                ),
            )

    def list_records(self) -> list[ApplicationRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    source, job_id, job_title, company, location, job_url, match_score,
                    matched_skills, status, search_query, resume_docx_path, resume_text_path,
                    cover_letter_path, recruiter_pitch_path, notes, applied_at, last_updated_at
                FROM job_applications
                ORDER BY last_updated_at DESC
                """
            ).fetchall()

        return [
            ApplicationRecord(
                source=row[0],
                job_id=row[1],
                job_title=row[2],
                company=row[3],
                location=row[4],
                job_url=row[5],
                match_score=row[6],
                matched_skills=json.loads(row[7] or "[]"),
                status=row[8],
                search_query=row[9],
                resume_docx_path=row[10],
                resume_text_path=row[11],
                cover_letter_path=row[12],
                recruiter_pitch_path=row[13],
                notes=row[14],
                applied_at=datetime.fromisoformat(row[15]) if row[15] else None,
                last_updated_at=datetime.fromisoformat(row[16]),
            )
            for row in rows
        ]

    def get_record(self, source: str, job_id: str) -> ApplicationRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    source, job_id, job_title, company, location, job_url, match_score,
                    matched_skills, status, search_query, resume_docx_path, resume_text_path,
                    cover_letter_path, recruiter_pitch_path, notes, applied_at, last_updated_at
                FROM job_applications
                WHERE source = ? AND job_id = ?
                """,
                (source, job_id),
            ).fetchone()

        if not row:
            return None

        return ApplicationRecord(
            source=row[0],
            job_id=row[1],
            job_title=row[2],
            company=row[3],
            location=row[4],
            job_url=row[5],
            match_score=row[6],
            matched_skills=json.loads(row[7] or "[]"),
            status=row[8],
            search_query=row[9],
            resume_docx_path=row[10],
            resume_text_path=row[11],
            cover_letter_path=row[12],
            recruiter_pitch_path=row[13],
            notes=row[14],
            applied_at=datetime.fromisoformat(row[15]) if row[15] else None,
            last_updated_at=datetime.fromisoformat(row[16]),
        )

