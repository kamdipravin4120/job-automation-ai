from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from src.apply.linkedin_easy_apply import LinkedInEasyApplyBot
from src.matcher.engine import JobMatcher
from src.models import ApplicationRecord, CandidateProfile, GeneratedArtifacts, JobMatchResult, JobPosting
from src.resume.engine import ResumeService
from src.scraper.service import ScraperService
from src.tracking.notion_sync import NotionApplicationTrackingSync
from src.tracking.service import TrackingService
from src.utils.config import AppConfig
from src.utils.files import ensure_parent_dir, resolve_path


class JobApplicationPipeline:
    def __init__(self, config: AppConfig, config_path: Path, logger: logging.Logger) -> None:
        self.config = config
        self.config_path = config_path
        self.config_dir = config_path.parent
        self.logger = logger.getChild("pipeline")

        self.scraper = ScraperService(config, self.config_dir, logger)
        self.matcher = JobMatcher(config.matcher, logger)
        self.resume_service = ResumeService(config.resume, self.config_dir, logger)
        self.tracking = TrackingService(config.tracking, self.config_dir, logger)
        self.notion_sync = NotionApplicationTrackingSync(config.notion, logger)
        self.easy_apply_bot = LinkedInEasyApplyBot(config.apply, self.config_dir, logger)

        self._jobs_cache: list[JobPosting] | None = None
        self._match_cache: list[JobMatchResult] | None = None

    def run(self, skip_apply: bool = False) -> None:
        self.scrape_jobs(sync_tracking=False)
        self.match_jobs(sync_tracking=False)
        self.generate_resume_assets(sync_tracking=False)
        if not skip_apply and self.config.apply.enabled:
            self.apply_to_jobs(sync_tracking=False)
        self.sync_tracking_records()

    def load_profile(self) -> CandidateProfile:
        profile_path = resolve_path(self.config_dir, self.config.app.profile_path)
        with profile_path.open("r", encoding="utf-8") as handle:
            raw_profile = json.load(handle)
        try:
            return CandidateProfile.model_validate(raw_profile)
        except ValidationError as exc:
            raise ValueError(f"Invalid profile.json structure: {exc}") from exc

    def scrape_jobs(self, sync_tracking: bool = True) -> list[JobPosting]:
        jobs = self.scraper.scrape()
        self._jobs_cache = jobs
        self._persist_jobs(jobs)

        for job in jobs:
            self.tracking.upsert_record(
                ApplicationRecord(
                    source=job.source,
                    job_id=job.job_id,
                    job_title=job.title,
                    company=job.company,
                    location=job.location,
                    job_url=job.url,
                    status="scraped",
                    search_query=job.search_query,
                )
            )
        if sync_tracking:
            self.sync_tracking_records()
        return jobs

    def match_jobs(self, sync_tracking: bool = True) -> list[JobMatchResult]:
        jobs = self._jobs_cache
        if not jobs:
            jobs = self._load_persisted_jobs()
            self._jobs_cache = jobs

        if not jobs:
            self.logger.info("No cached or persisted jobs found, starting scrape...")
            jobs = self.scrape_jobs(sync_tracking=False)

        profile = self.load_profile()
        matches = self.matcher.rank_jobs(profile=profile, jobs=jobs)
        self._match_cache = matches

        for match in matches:
            self.tracking.upsert_record(
                ApplicationRecord(
                    source=match.job.source,
                    job_id=match.job.job_id,
                    job_title=match.job.title,
                    company=match.job.company,
                    location=match.job.location,
                    job_url=match.job.url,
                    match_score=match.total_score,
                    matched_skills=match.matched_skills,
                    status="matched",
                    search_query=match.job.search_query,
                )
            )
        if sync_tracking:
            self.sync_tracking_records()
        return matches

    def generate_resume_assets(self, sync_tracking: bool = True) -> list[ApplicationRecord]:
        matches = self._match_cache or self.match_jobs(sync_tracking=False)
        profile = self.load_profile()
        top_matches = matches[: self.config.app.top_matches_to_process]
        prepared_records: list[ApplicationRecord] = []

        for match in top_matches:
            bundle, artifacts = self.resume_service.build_assets(profile=profile, job=match.job)
            prepared_records.append(self._build_prepared_record(match, artifacts))

        if sync_tracking:
            self.sync_tracking_records()
        return prepared_records

    def apply_to_jobs(
        self,
        limit: int | None = None,
        sync_tracking: bool = True,
    ) -> list[ApplicationRecord]:
        records = self.tracking.actionable_records()
        updated_records = self.easy_apply_bot.apply(records, limit=limit)
        for record in updated_records:
            record.last_updated_at = datetime.now(UTC)
            if record.status == "applied":
                record.applied_at = datetime.now(UTC)
            self.tracking.upsert_record(record)
        if sync_tracking:
            self.sync_tracking_records()
        return updated_records

    def sync_tracking_records(self) -> None:
        try:
            self.notion_sync.sync_records(self.tracking.list_records())
        except Exception as exc:
            self.logger.exception("Notion tracking sync failed: %s", exc)

    def _build_prepared_record(
        self,
        match: JobMatchResult,
        artifacts: GeneratedArtifacts,
    ) -> ApplicationRecord:
        record = ApplicationRecord(
            source=match.job.source,
            job_id=match.job.job_id,
            job_title=match.job.title,
            company=match.job.company,
            location=match.job.location,
            job_url=match.job.url,
            match_score=match.total_score,
            matched_skills=match.matched_skills,
            status="resume_generated",
            search_query=match.job.search_query,
            resume_docx_path=artifacts.resume_docx_path,
            resume_text_path=artifacts.resume_text_path,
            cover_letter_path=artifacts.cover_letter_path,
            recruiter_pitch_path=artifacts.recruiter_pitch_path,
        )
        self.tracking.upsert_record(record)
        return record

    def _persist_jobs(self, jobs: list[JobPosting]) -> None:
        output_path = resolve_path(self.config_dir, self.config.app.job_dump_path)
        ensure_parent_dir(output_path)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump([job.model_dump() for job in jobs], handle, indent=2)

    def _load_persisted_jobs(self) -> list[JobPosting] | None:
        path = resolve_path(self.config_dir, self.config.app.job_dump_path)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return [JobPosting.model_validate(j) for j in data]
        except Exception as exc:
            self.logger.warning("Could not load persisted jobs from %s: %s", path, exc)
            return None
