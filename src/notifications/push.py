from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger("notifications.push")


@dataclass
class PushEvent:
    title: str
    body: str
    data: dict[str, Any] = field(default_factory=dict)
    priority: str = "default"


class PushService:
    def __init__(
        self,
        ntfy_topic_url: str | None = None,
        fcm_project_id: str | None = None,
        fcm_service_account_json: str | None = None,
    ) -> None:
        self.ntfy_topic_url = ntfy_topic_url
        self.fcm_project_id = fcm_project_id
        self.fcm_service_account_json = fcm_service_account_json
        self._fcm_tokens: list[str] = []

    def register_fcm_token(self, token: str) -> None:
        if token not in self._fcm_tokens:
            self._fcm_tokens.append(token)

    def unregister_fcm_token(self, token: str) -> None:
        self._fcm_tokens = [t for t in self._fcm_tokens if t != token]

    def send_event(self, event: PushEvent, tokens: list[str] | None = None) -> None:
        self.send_ntfy(event)
        self.send_fcm_all(event, tokens=tokens or [])

    def send_ntfy(self, event: PushEvent) -> None:
        if not self.ntfy_topic_url:
            return
        try:
            resp = httpx.post(
                self.ntfy_topic_url,
                data=event.body.encode(),
                headers={
                    "Title": event.title,
                    "Priority": event.priority,
                    "Content-Type": "text/plain",
                },
                timeout=5.0,
            )
            resp.raise_for_status()
        except Exception as exc:
            log.warning("ntfy push failed: %s", exc)

    def send_fcm_all(self, event: PushEvent, tokens: list[str] | None = None) -> None:
        effective_tokens = tokens if tokens is not None else self._fcm_tokens
        if not effective_tokens or not self.fcm_project_id:
            return
        for token in list(effective_tokens):
            try:
                self._send_fcm_one(token, event)
            except Exception as exc:
                log.warning("FCM push to token %s... failed: %s", token[:12], exc)

    def _send_fcm_one(self, token: str, event: PushEvent) -> None:
        access_token = self._get_fcm_access_token()
        url = f"https://fcm.googleapis.com/v1/projects/{self.fcm_project_id}/messages:send"
        payload = {
            "message": {
                "token": token,
                "notification": {"title": event.title, "body": event.body},
                "data": {k: str(v) for k, v in event.data.items()},
            }
        }
        resp = httpx.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        resp.raise_for_status()

    def _get_fcm_access_token(self) -> str:
        import google.auth.transport.requests
        import google.oauth2.service_account
        if not self.fcm_service_account_json:
            raise RuntimeError("FCM_SERVICE_ACCOUNT_JSON not configured")
        creds = google.oauth2.service_account.Credentials.from_service_account_file(
            self.fcm_service_account_json,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"],
        )
        creds.refresh(google.auth.transport.requests.Request())
        return creds.token
