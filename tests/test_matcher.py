from __future__ import annotations

import logging
import unittest

from src.matcher.engine import JobMatcher
from src.models import CandidateProfile, JobPosting
from src.utils.config import MatcherConfig, MatcherWeights


class FakeEmbeddingClient:
    def __init__(self, responses: list[list[list[float]]]) -> None:
        self._responses = responses

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = self._responses.pop(0)
        if len(response) != len(texts):
            raise AssertionError("Unexpected embedding batch length")
        return response


def build_profile() -> CandidateProfile:
    return CandidateProfile(
        name="Test Candidate",
        email="test@example.com",
        phone="+1-555-555-5555",
        location="Remote",
        headline="Senior Python Engineer",
        summary="Builds backend systems and automation flows.",
        preferred_titles=["Senior Python Engineer", "AI Engineer"],
        skills=["Python", "Playwright", "OpenAI"],
    )


class JobMatcherTests(unittest.TestCase):
    def test_job_matcher_ranks_and_filters_jobs(self) -> None:
        profile = build_profile()
        jobs = [
            JobPosting(
                source="linkedin",
                job_id="job-1",
                title="Senior Python Engineer",
                company="Acme",
                location="Remote",
                description="Python Playwright OpenAI backend automation",
                url="https://example.com/jobs/1",
            ),
            JobPosting(
                source="linkedin",
                job_id="job-2",
                title="Frontend Developer",
                company="Beta",
                location="Remote",
                description="React CSS UI",
                url="https://example.com/jobs/2",
            ),
        ]
        matcher = JobMatcher(
            MatcherConfig(
                min_score=0.2,
                top_k=5,
                weights=MatcherWeights(description=0.6, title=0.25, skills=0.15),
            ),
            logging.getLogger("test_matcher"),
            embedding_client=FakeEmbeddingClient(
                responses=[
                    [
                        [1.0, 0.0],
                        [0.99, 0.01],
                        [0.05, 0.95],
                    ],
                    [
                        [1.0, 0.0],
                        [0.98, 0.02],
                        [0.10, 0.90],
                    ],
                ]
            ),
        )

        ranked = matcher.rank_jobs(profile=profile, jobs=jobs)

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].job.job_id, "job-1")
        self.assertEqual(ranked[0].matched_skills, ["Python", "Playwright", "OpenAI"])
        self.assertGreater(ranked[0].total_score, 0.9)


if __name__ == "__main__":
    unittest.main()
