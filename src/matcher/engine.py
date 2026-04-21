from __future__ import annotations

import logging

from src.matcher.openai_embeddings import OpenAIEmbeddingClient
from src.models import CandidateProfile, JobMatchResult, JobPosting
from src.utils.config import MatcherConfig
from src.utils.text import cosine_similarity, skill_overlap_ratio


class JobMatcher:
    def __init__(
        self,
        config: MatcherConfig,
        logger: logging.Logger,
        embedding_client: OpenAIEmbeddingClient | None = None,
    ) -> None:
        self.config = config
        self.logger = logger.getChild("matcher")
        self.embedding_client = embedding_client or OpenAIEmbeddingClient(config, self.logger)

    def rank_jobs(
        self,
        *,
        profile: CandidateProfile,
        jobs: list[JobPosting],
    ) -> list[JobMatchResult]:
        if not jobs:
            return []

        try:
            return self._rank_jobs_with_embeddings(profile, jobs)
        except Exception as exc:
            self.logger.warning("Embedding-based ranking failed, using keyword fallback: %s", exc)
            from src.matcher.keyword_matcher import KeywordMatcherFallback

            return KeywordMatcherFallback(self.config, self.logger).rank_jobs(profile, jobs)

    def _rank_jobs_with_embeddings(
        self, profile: CandidateProfile, jobs: list[JobPosting]
    ) -> list[JobMatchResult]:
        profile_text = profile.as_embedding_text()
        title_target_text = ", ".join(profile.preferred_titles) or profile.headline

        description_embeddings = self.embedding_client.embed_texts(
            [profile_text, *[job.searchable_text() for job in jobs]]
        )
        title_embeddings = self.embedding_client.embed_texts(
            [title_target_text, *[job.title for job in jobs]]
        )

        profile_description_embedding = description_embeddings[0]
        profile_title_embedding = title_embeddings[0]
        description_job_embeddings = description_embeddings[1:]
        title_job_embeddings = title_embeddings[1:]

        ranked_results: list[JobMatchResult] = []
        for job, description_embedding, title_embedding in zip(
            jobs,
            description_job_embeddings,
            title_job_embeddings,
        ):
            description_similarity = cosine_similarity(
                profile_description_embedding,
                description_embedding,
            )
            title_similarity = cosine_similarity(profile_title_embedding, title_embedding)
            skill_overlap, matched_skills = skill_overlap_ratio(profile.skills, job.searchable_text())
            total_score = (
                (self.config.weights.description * description_similarity)
                + (self.config.weights.title * title_similarity)
                + (self.config.weights.skills * skill_overlap)
            )

            if total_score < self.config.min_score:
                continue

            ranked_results.append(
                JobMatchResult(
                    job=job,
                    description_similarity=description_similarity,
                    title_similarity=title_similarity,
                    skill_overlap=skill_overlap,
                    total_score=total_score,
                    matched_skills=matched_skills,
                )
            )

        ranked_results.sort(key=lambda item: item.total_score, reverse=True)
        return ranked_results[: self.config.top_k]
