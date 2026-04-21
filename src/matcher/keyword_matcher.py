from __future__ import annotations
import re
import logging
from src.models import CandidateProfile, JobMatchResult, JobPosting
from src.utils.text import normalize_text, skill_overlap_ratio

class KeywordMatcherFallback:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger.getChild("keyword_fallback")

    def rank_jobs(self, profile: CandidateProfile, jobs: list[JobPosting]) -> list[JobMatchResult]:
        self.logger.info("Ranking jobs using keyword-based fallback...")
        ranked_results: list[JobMatchResult] = []
        
        profile_keywords = self._extract_keywords(profile.as_embedding_text())
        title_keywords = self._extract_keywords(", ".join(profile.preferred_titles))

        for job in jobs:
            job_text = job.searchable_text()
            job_keywords = self._extract_keywords(job_text)
            job_title_keywords = self._extract_keywords(job.title)

            # Description similarity (overlap)
            desc_sim = self._calculate_overlap(profile_keywords, job_keywords)
            # Title similarity
            title_sim = self._calculate_overlap(title_keywords, job_title_keywords)
            # Skill overlap
            skill_overlap, matched_skills = skill_overlap_ratio(profile.skills, job_text)

            total_score = (
                (self.config.weights.description * desc_sim)
                + (self.config.weights.title * title_sim)
                + (self.config.weights.skills * skill_overlap)
            )

            if total_score < self.config.min_score:
                continue

            ranked_results.append(
                JobMatchResult(
                    job=job,
                    description_similarity=desc_sim,
                    title_similarity=title_sim,
                    skill_overlap=skill_overlap,
                    total_score=total_score,
                    matched_skills=matched_skills,
                )
            )

        ranked_results.sort(key=lambda item: item.total_score, reverse=True)
        return ranked_results[: self.config.top_k]

    def _extract_keywords(self, text: str) -> set[str]:
        words = re.findall(r"\w+", text.lower())
        # Filter out very common short words
        return {w for w in words if len(w) > 3}

    def _calculate_overlap(self, set1: set[str], set2: set[str]) -> float:
        if not set1 or not set2:
            return 0.0
        intersection = set1.intersection(set2)
        # Use simple overlap ratio
        return len(intersection) / len(set1)
