from __future__ import annotations

import json
import logging

import anthropic

from src.models import CandidateProfile, JobPosting, TailoredResumeBundle
from src.utils.config import ResumeConfig
from src.utils.retry import retry_sync
from src.utils.text import extract_json_object

SYSTEM_PROMPT = """
You tailor resumes for ATS and recruiter review.
Rules:
- Never invent companies, titles, dates, degrees, certifications, or achievements not present in the profile.
- Prefer exact terminology from the job description when it is truthful for the candidate.
- Keep the output ATS-safe: plain text, single-column language, no tables, no graphics, no emojis.
- Produce concise, high-signal bullet points with measurable impact when the profile supports it.
- Return valid JSON only and no markdown fences.
""".strip()


class ClaudeResumeClient:
    def __init__(self, config: ResumeConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger.getChild("claude_resume")
        self.client = anthropic.Anthropic()

    @retry_sync(attempts=3)
    def tailor_resume(
        self,
        *,
        profile: CandidateProfile,
        job: JobPosting,
    ) -> TailoredResumeBundle:
        prompt = f"""
Candidate profile JSON:
{profile.model_dump_json(indent=2)}

Job posting JSON:
{job.model_dump_json(indent=2)}

Return JSON with exactly these top-level keys:
headline
summary
skills
experience
education
projects
certifications
resume_text
recruiter_pitch
cover_letter

Requirements:
- `skills` must be a list of strings.
- `experience` must be a list of objects with keys: title, company, location, dates, bullets.
- `education` must be a list of objects with keys: degree, institution, year.
- `projects` must be a list of objects with keys: name, description.
- `resume_text` must be ATS-safe plain text with clear section headers.
- `recruiter_pitch` must be 4-6 sentences.
- `cover_letter` must be 250-350 words.
- Preserve factual accuracy from the profile.
""".strip()

        response = self.client.messages.create(
            model=self.config.claude_model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        payload = extract_json_object(raw_text)
        payload["job_id"] = job.job_id
        payload["source"] = job.source
        self.logger.info("Claude generated tailored resume bundle for %s", job.job_id)
        return TailoredResumeBundle.model_validate(payload)

    @retry_sync(attempts=3)
    def extract_profile_from_resume(self, resume_text: str) -> CandidateProfile:
        prompt = f"""
Analyze the following resume text and extract the candidate's profile in JSON format.
Return ONLY valid JSON with no markdown formatting.

Exactly follow this JSON structure:
{{
  "name": "full name",
  "email": "email address",
  "phone": "phone number",
  "location": "city, country",
  "headline": "professional headline",
  "summary": "quick professional summary",
  "preferred_titles": ["title 1", "title 2"],
  "skills": ["skill 1", "skill 2"],
  "experience": [
    {{
      "title": "role",
      "company": "company",
      "location": "location",
      "dates": "dates",
      "bullets": ["achievement 1", "achievement 2"]
    }}
  ],
  "education": [
    {{
      "degree": "degree",
      "institution": "institution",
      "year": "year"
    }}
  ],
  "projects": [
    {{
      "name": "project name",
      "description": "description"
    }}
  ],
  "certifications": ["cert 1", "cert 2"]
}}

Resume text:
{resume_text}
"""
        response = self.client.messages.create(
            model=self.config.claude_model,
            max_tokens=self.config.max_tokens,
            temperature=0.1,
            system="You are a professional recruiting analyst.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        payload = extract_json_object(raw_text)
        self.logger.info("Claude successfully extracted candidate profile from resume.")
        return CandidateProfile.model_validate(payload)

