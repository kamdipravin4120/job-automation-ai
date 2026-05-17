from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

import yaml
from pydantic import BaseModel, Field

SelectorConfigValue: TypeAlias = str | list[str]


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file_path: str = "logs/job_automation.log"


class SearchQueryConfig(BaseModel):
    keywords: str
    location: str

    @property
    def slug(self) -> str:
        return f"{self.keywords}::{self.location}"


class ScraperSourceConfig(BaseModel):
    enabled: bool = True
    headless: bool = False
    max_jobs_per_query: int = 10
    timeout_ms: int = 30000
    storage_state_path: str
    search_url_template: str
    selectors: dict[str, SelectorConfigValue] = Field(default_factory=dict)


class ScraperConfig(BaseModel):
    linkedin: ScraperSourceConfig
    naukri: ScraperSourceConfig
    indeed: ScraperSourceConfig
    glassdoor: ScraperSourceConfig


class MatcherWeights(BaseModel):
    description: float = 0.55
    title: float = 0.25
    skills: float = 0.20


class MatcherConfig(BaseModel):
    model: str = "text-embedding-3-small"
    batch_size: int = 32
    top_k: int = 10
    min_score: float = 0.45
    dimensions: int | None = None
    weights: MatcherWeights = Field(default_factory=MatcherWeights)


class ResumeConfig(BaseModel):
    provider: str = "claude"  # "claude" or "gemini"
    claude_model: str = "claude-sonnet-4-20250514"
    gemini_model: str = "gemini-1.5-pro"
    temperature: float = 0.2
    max_tokens: int = 4096
    docx_output_dir: str = "artifacts/resumes"
    cover_letter_output_dir: str = "artifacts/covers"
    pitch_output_dir: str = "artifacts/pitches"
    font_name: str = "Arial"
    font_size: int = 11


class ApplyConfig(BaseModel):
    enabled: bool = True
    headless: bool = False
    manual_review_required: bool = True
    max_applications_per_run: int = 5
    timeout_ms: int = 30000
    storage_state_path: str = "artifacts/browser/linkedin_state.json"
    resume_file_input_selector: str = "input[type='file']"
    easy_apply_button_selector: str = "button.jobs-apply-button"
    next_button_selector: str = "button:has-text('Next')"
    review_button_selector: str = "button:has-text('Review')"
    submit_button_selector: str = "button:has-text('Submit application')"
    dismiss_button_selector: str = "button:has-text('Done')"
    progress_step_selector: str = ".artdeco-completeness-meter-linear__progress-element"
    upload_wait_ms: int = 1500
    human_delay_min_ms: int = 700
    human_delay_max_ms: int = 1800
    login_check_selector: SelectorConfigValue = Field(
        default=["img.global-nav__me-photo", "button.global-nav__primary-link-me-menu-trigger"]
    )


class TrackingConfig(BaseModel):
    mode: str = "sqlite"
    sqlite_path: str = "artifacts/job_tracker.db"
    csv_path: str = "artifacts/job_tracker.csv"


class NotionSyncConfig(BaseModel):
    enabled: bool = False
    api_key_env_var: str = "NOTION_API_KEY"
    api_base_url: str = "https://api.notion.com/v1"
    notion_version: str = "2026-03-11"
    request_timeout_sec: int = 30
    application_tracking_data_source_id: str = ""
    max_records_per_sync: int = 200


class AppSection(BaseModel):
    profile_path: str = "data/profile.json"
    job_dump_path: str = "artifacts/jobs/jobs.json"
    top_matches_to_process: int = 5
    output_dir: str = "artifacts"


class AppConfig(BaseModel):
    app: AppSection = Field(default_factory=AppSection)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    search_queries: list[SearchQueryConfig] = Field(default_factory=list)
    scraper: ScraperConfig
    matcher: MatcherConfig = Field(default_factory=MatcherConfig)
    resume: ResumeConfig = Field(default_factory=ResumeConfig)
    apply: ApplyConfig = Field(default_factory=ApplyConfig)
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)
    notion: NotionSyncConfig = Field(default_factory=NotionSyncConfig)


def load_config(path: Path) -> AppConfig:
    with path.open("r", encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle) or {}
    return AppConfig.model_validate(raw_config)
