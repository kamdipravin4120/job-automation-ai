from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.models import CandidateProfile, GeneratedArtifacts, JobPosting, TailoredResumeBundle
from src.utils.config import ResumeConfig

class ResumeService:
    def __init__(self, config: ResumeConfig, config_dir: Path, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger.getChild("resume")
        
        # Instantiate the correct provider client
        if self.config.provider == "gemini":
            from src.resume.gemini_client import GeminiResumeClient
            self.ai_client = GeminiResumeClient(config, self.logger)
        else:
            from src.resume.claude_client import ClaudeResumeClient
            self.ai_client = ClaudeResumeClient(config, self.logger)
            
        from src.resume.docx_generator import ATSSafeResumeDocxGenerator
        self.docx_generator = ATSSafeResumeDocxGenerator(config, config_dir)

    def build_assets(
        self,
        *,
        profile: CandidateProfile,
        job: JobPosting,
    ) -> tuple[TailoredResumeBundle, GeneratedArtifacts]:
        try:
            bundle = self.ai_client.tailor_resume(profile=profile, job=job)
        except Exception as exc:
            self.logger.warning(
                "AI tailoring failed for %s, falling back to static generation: %s", job.job_id, exc
            )
            from src.resume.static_generator import StaticResumeGenerator
            bundle = StaticResumeGenerator(self.logger).generate(profile, job)

        artifacts = self.docx_generator.write_bundle(profile=profile, job=job, bundle=bundle)
        return bundle, artifacts

    def analyze_resume_text(self, text: str) -> CandidateProfile:
        """Utility for dashboard to parse uploaded resume files."""
        return self.ai_client.extract_profile_from_resume(text)

    def analyze_linkedin_text(self, text: str) -> dict:
        """New: Strategy analysis for LinkedIn profile optimization."""
        return self.ai_client.analyze_linkedin_profile(text)

    def generate_interview_briefing(self, profile: CandidateProfile, job: JobPosting) -> list[dict]:
        """New: Generate tactical briefing for interview prep."""
        return self.ai_client.generate_interview_briefing(profile, job)
