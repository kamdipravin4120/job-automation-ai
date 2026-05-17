from __future__ import annotations

import re
from dataclasses import dataclass
from email.utils import parseaddr

_COMPANY_PROMPT = """\
Extract the recruiter's name, email address, and company from this email.
Reply with exactly three lines:
NAME: <full name or UNKNOWN>
EMAIL: <email address or UNKNOWN>
COMPANY: <company name or UNKNOWN>

No extra text.

From: {sender}
Subject: {subject}

Body:
{body}"""


@dataclass
class RecruiterContact:
    name: str | None
    email: str | None
    company: str | None

    def as_dict(self) -> dict:
        return {k: v for k, v in {"name": self.name, "email": self.email, "company": self.company}.items() if v}


def _parse_field(lines: list[str], prefix: str) -> str | None:
    for line in lines:
        if line.upper().startswith(prefix + ":"):
            val = line[len(prefix) + 1:].strip()
            return val if val and val.upper() != "UNKNOWN" else None
    return None


def extract_recruiter(*, sender: str, subject: str, body: str, gemini_model=None) -> RecruiterContact:
    parsed_name, parsed_email = parseaddr(sender)
    name = parsed_name.strip() or None
    email = parsed_email.strip().lower() or None

    company: str | None = None
    if gemini_model is not None:
        try:
            prompt = _COMPANY_PROMPT.format(
                sender=sender[:200],
                subject=subject[:200],
                body=body[:1500],
            )
            resp = gemini_model.generate_content(prompt)
            lines = resp.text.strip().splitlines()
            if not name:
                name = _parse_field(lines, "NAME")
            if not email:
                email = _parse_field(lines, "EMAIL")
            company = _parse_field(lines, "COMPANY")
        except Exception:
            pass

    if not company and email:
        domain = email.split("@")[-1] if "@" in email else ""
        if domain and not _is_free_provider(domain):
            company = domain.split(".")[0].capitalize()

    return RecruiterContact(name=name, email=email, company=company)


_FREE_PROVIDERS = frozenset({
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "icloud.com", "protonmail.com", "live.com", "me.com",
})


def _is_free_provider(domain: str) -> bool:
    return domain.lower() in _FREE_PROVIDERS
