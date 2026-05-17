from __future__ import annotations

from enum import Enum


class EmailStatus(str, Enum):
    REJECTION = "rejection"
    INTERVIEW_REQUEST = "interview_request"
    OFFER = "offer"
    FOLLOW_UP_NEEDED = "follow_up_needed"
    OTHER = "other"


_VALID_STATUSES = {s.value for s in EmailStatus}

_PROMPT = """\
Classify this recruiter email into exactly one of these categories:
  rejection, interview_request, offer, follow_up_needed, other

Reply with only the category name — no punctuation, no explanation.

Subject: {subject}

Body:
{body}"""


def classify_email(subject: str, body: str, gemini_model) -> EmailStatus:
    prompt = _PROMPT.format(subject=subject[:200], body=body[:1500])
    response = gemini_model.generate_content(prompt)
    raw = response.text.strip().lower()
    return EmailStatus(raw) if raw in _VALID_STATUSES else EmailStatus.OTHER
