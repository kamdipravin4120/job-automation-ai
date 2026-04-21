from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class ExperienceItem(BaseModel):
    title: str
    company: str
    location: str | None = None
    dates: str
    bullets: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    degree: str
    institution: str
    year: str


class ProjectItem(BaseModel):
    name: str
    description: str


class CandidateProfile(BaseModel):
    name: str
    email: str
    phone: str
    location: str
    linkedin: HttpUrl | None = None
    portfolio: HttpUrl | None = None
    headline: str
    summary: str
    preferred_titles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)

    def as_embedding_text(self) -> str:
        experience_lines: list[str] = []
        for item in self.experience:
            experience_lines.append(
                " | ".join(
                    part
                    for part in [
                        item.title,
                        item.company,
                        item.location or "",
                        item.dates,
                        " ".join(item.bullets),
                    ]
                    if part
                )
            )
        return "\n".join(
            [
                self.headline,
                self.summary,
                f"Preferred roles: {', '.join(self.preferred_titles)}",
                f"Skills: {', '.join(self.skills)}",
                *experience_lines,
                *[f"{item.degree} - {item.institution} ({item.year})" for item in self.education],
                *[f"{item.name}: {item.description}" for item in self.projects],
                f"Certifications: {', '.join(self.certifications)}",
            ]
        )


class JobPosting(BaseModel):
    source: str
    job_id: str
    title: str
    company: str
    location: str
    description: str = ""
    url: str
    search_query: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    def searchable_text(self) -> str:
        return "\n".join(
            [
                self.title,
                self.company,
                self.location,
                self.description,
                self.search_query,
            ]
        )


class JobMatchResult(BaseModel):
    job: JobPosting
    description_similarity: float
    title_similarity: float
    skill_overlap: float
    total_score: float
    matched_skills: list[str] = Field(default_factory=list)


class TailoredResumeBundle(BaseModel):
    job_id: str
    source: str
    headline: str
    summary: str
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    resume_text: str
    recruiter_pitch: str
    cover_letter: str


class GeneratedArtifacts(BaseModel):
    resume_docx_path: str
    resume_text_path: str
    cover_letter_path: str
    recruiter_pitch_path: str


class ApplicationRecord(BaseModel):
    source: str
    job_id: str
    job_title: str
    company: str
    location: str
    job_url: str
    match_score: float = 0.0
    matched_skills: list[str] = Field(default_factory=list)
    status: str
    search_query: str = ""
    resume_docx_path: str | None = None
    resume_text_path: str | None = None
    cover_letter_path: str | None = None
    recruiter_pitch_path: str | None = None
    notes: str = ""
    applied_at: datetime | None = None
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
