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


def classify_email(subject: str, body: str, anthropic_client) -> EmailStatus:
    prompt = _PROMPT.format(subject=subject[:200], body=body[:1500])
    response = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip().lower()
    return EmailStatus(raw) if raw in _VALID_STATUSES else EmailStatus.OTHER
