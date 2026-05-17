from __future__ import annotations

import json
import logging
import os

import google.generativeai as genai

from src.models import CandidateProfile, JobPosting, TailoredResumeBundle
from src.utils.config import ResumeConfig
from src.utils.retry import retry_sync
from src.utils.text import extract_json_object

class GeminiResumeClient:
    def __init__(self, config: ResumeConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger.getChild("gemini_resume")
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            self.logger.error("GEMINI_API_KEY not found in environment.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(self.config.gemini_model)

    @retry_sync(attempts=3)
    def tailor_resume(
        self,
        *,
        profile: CandidateProfile,
        job: JobPosting,
    ) -> TailoredResumeBundle:
        prompt = f"""
You tailor resumes for ATS and recruiter review.
Rules:
- Never invent companies, titles, dates, degrees, certifications, or achievements not present in the profile.
- Prefer exact terminology from the job description when it is truthful for the candidate.
- Keep the output ATS-safe: plain text, single-column language, no tables, no graphics, no emojis.
- Produce concise, high-signal bullet points with measurable impact when the profile supports it.
- Return valid JSON only.

Candidate profile JSON:
{profile.model_dump_json(indent=2)}

Job posting JSON:
{job.model_dump_json(indent=2)}

Return JSON with exactly these top-level keys:
- headline
- summary
- skills
- experience
- education
- projects
- certifications
- resume_text
- recruiter_pitch
- cover_letter

Requirements:
- `skills` must be a list of strings.
- `experience` must be a list of objects with keys: title, company, location, dates, bullets.
- `education` must be a list of objects with keys: degree, institution, year.
- `projects` must be a list of objects with keys: name, description.
- `resume_text` must be ATS-safe plain text with clear section headers.
- `recruiter_pitch` must be 4-6 sentences.
- `cover_letter` must be 250-350 words.
- Preserve factual accuracy from the profile.
"""
        response = self.model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_tokens,
            ),
        )
        payload = extract_json_object(response.text)
        payload["job_id"] = job.job_id
        payload["source"] = job.source
        self.logger.info("Gemini generated tailored resume bundle for %s", job.job_id)
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
        response = self.model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=self.config.max_tokens,
            ),
        )
        payload = extract_json_object(response.text)
        self.logger.info("Gemini successfully extracted candidate profile from resume.")
        return CandidateProfile.model_validate(payload)

    @retry_sync(attempts=3)
    def analyze_linkedin_profile(self, linkedin_text: str) -> dict:
        """New: Executive Brand Strategy Analysis."""
        prompt = f"""
You are an Executive Branding Strategist specializing in CTO and VP-level roles.
Analyze this LinkedIn profile PDF export and provide an 'Elite' brand calibration.

Rules:
- Headline: Must be high-impact, keyword-rich (industry, specific role, ROI/Impact).
- Summary: Professional, concise, focusing on leadership and strategic outcomes.
- Recommendations: Specific, actionable tips for market positioning (e.g., 'Highlight your international M&A experience more').
- Return ONLY valid JSON.

LinkedIn Text:
{linkedin_text}

Return JSON with exactly these keys:
- headline
- summary
- recommendations (list of strings)
"""
        response = self.model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=2048,
            ),
        )
        return extract_json_object(response.text)

    @retry_sync(attempts=3)
    def generate_interview_briefing(self, profile: CandidateProfile, job: JobPosting) -> list[dict]:
        """New: Generate Tactical Drill Questions & STAR Points."""
        self.logger.info("Generating tactical briefing for job: %s", job.job_id)
        prompt = f"""
You are an Elite Interview Coach for CTO and VP-level Engineering candidates.
Generate a 'Combat Briefing' for a candidate preparing for an interview with the following details.

# Candidate Career DNA (JSON):
{profile.model_dump_json(indent=2)}

# Target Job Intelligence (JSON):
{job.model_dump_json(indent=2)}

Your task:
Analyze the JD requirements and the candidate's history to produce 5-7 high-probability interview questions (3 Behavioral/Leadership, 2 Technical/Strategic, 2 ROI-focused).

For each question, provide:
1. 'question': The likely interview question.
2. 'rationale': Why an elite employer is asking this (the hidden objective).
3. 'star_points': 3-4 specific STAR points from the candidate's profile that they should use in their answer.

Return ONLY a valid JSON list of objects with these keys:
- question
- rationale
- star_points (list of strings)
"""
        response = self.model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=3072,
            ),
        )
        return extract_json_object(response.text)
