from __future__ import annotations

import base64
from dataclasses import dataclass

from googleapiclient.discovery import build


@dataclass
class EmailMessage:
    message_id: str
    subject: str
    sender: str
    date: str
    body: str


class GmailClient:
    def __init__(self, credentials) -> None:
        self._creds = credentials

    def _service(self):
        return build("gmail", "v1", credentials=self._creds)

    def list_unread(self, max_results: int = 50, query: str = "is:unread") -> list[EmailMessage]:
        svc = self._service()
        result = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        raw_messages = result.get("messages", [])
        if not raw_messages:
            return []
        emails = []
        for ref in raw_messages:
            msg = svc.users().messages().get(userId="me", id=ref["id"], format="full").execute()
            emails.append(self._parse(msg))
        return emails

    def _parse(self, msg: dict) -> EmailMessage:
        payload = msg.get("payload", {})
        headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
        body = self._extract_body(payload)
        return EmailMessage(
            message_id=msg["id"],
            subject=headers.get("Subject", ""),
            sender=headers.get("From", ""),
            date=headers.get("Date", ""),
            body=body,
        )

    def _extract_body(self, payload: dict) -> str:
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        return ""
