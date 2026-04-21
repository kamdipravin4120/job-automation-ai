from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def skill_overlap_ratio(profile_skills: Iterable[str], job_text: str) -> tuple[float, list[str]]:
    skills = [skill for skill in profile_skills]
    normalized_job_text = normalize_text(job_text).lower()
    matched_skills = [
        skill
        for skill in skills
        if skill.strip() and skill.strip().lower() in normalized_job_text
    ]
    total_skills = len(skills)
    if total_skills == 0:
        return 0.0, []
    return len(matched_skills) / total_skills, matched_skills


def extract_json_object(response_text: str) -> dict:
    if not response_text:
        raise ValueError("Empty response received from model")

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    start = response_text.find("{")
    end = response_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")
    return json.loads(response_text[start : end + 1])
