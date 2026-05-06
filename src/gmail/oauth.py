from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import requests

_DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


@dataclass
class DeviceCodeResponse:
    device_code: str
    user_code: str
    verification_url: str
    interval: int
    expires_in: int


class GmailOAuth:
    """Device-code OAuth flow for Gmail. No browser redirect needed."""

    def __init__(self, client_id: str, client_secret: str, token_path: str = ".gmail_token.json") -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_path = token_path
        self._device_code: str | None = None

    def init_device_flow(self) -> DeviceCodeResponse:
        resp = requests.post(
            _DEVICE_CODE_URL,
            data={"client_id": self.client_id, "scope": _GMAIL_SCOPE},
        )
        resp.raise_for_status()
        data = resp.json()
        self._device_code = data["device_code"]
        return DeviceCodeResponse(
            device_code=data["device_code"],
            user_code=data["user_code"],
            verification_url=data["verification_url"],
            interval=data.get("interval", 5),
            expires_in=data.get("expires_in", 1800),
        )

    def poll_for_token(self) -> str:
        if not self._device_code:
            raise RuntimeError("Call init_device_flow() first")
        resp = requests.post(
            _TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "device_code": self._device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            if data["error"] in ("authorization_pending", "slow_down"):
                return "pending"
            raise RuntimeError(f"OAuth error: {data['error']}")
        Path(self.token_path).write_text(json.dumps(data))
        return "authorized"

    def is_authorized(self) -> bool:
        p = Path(self.token_path)
        if not p.exists():
            return False
        try:
            token = json.loads(p.read_text())
            return bool(token.get("refresh_token") or token.get("access_token"))
        except (json.JSONDecodeError, KeyError):
            return False

    def get_credentials(self):
        from google.oauth2.credentials import Credentials
        token = json.loads(Path(self.token_path).read_text())
        return Credentials(
            token=token.get("access_token"),
            refresh_token=token.get("refresh_token"),
            token_uri=_TOKEN_URL,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
