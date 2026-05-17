from __future__ import annotations

import base64
import json
import pathlib
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.core.deps import get_current_device

router = APIRouter()

_BROWSER_DIR   = pathlib.Path("artifacts/browser")
_CREDS_FILE    = pathlib.Path("data/credentials.json")

_PLATFORMS = ("linkedin", "naukri")


def _session_info(platform: str) -> dict[str, Any]:
    state_file = _BROWSER_DIR / f"{platform}_state.json"
    if not state_file.exists():
        return {"status": "no_session", "session_at": None}
    mtime = state_file.stat().st_mtime
    session_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    # treat session as expired if older than 7 days (604800 seconds)
    age = datetime.now(tz=timezone.utc).timestamp() - mtime
    status = "expired" if age > 604800 else "connected"
    return {"status": status, "session_at": session_at}


def _load_creds() -> dict[str, Any]:
    if not _CREDS_FILE.exists():
        return {}
    try:
        return json.loads(_CREDS_FILE.read_text())
    except Exception:
        return {}


def _save_creds(data: dict[str, Any]) -> None:
    _CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CREDS_FILE.write_text(json.dumps(data, indent=2))


def _encode(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


def _decode(value: str) -> str:
    try:
        return base64.b64decode(value.encode()).decode()
    except Exception:
        return ""


class CredentialsOut(BaseModel):
    platforms: dict[str, Any]


class CredentialUpdateRequest(BaseModel):
    platform: str
    email: str
    password: str


@router.get("", response_model=CredentialsOut)
async def get_credentials(_device=Depends(get_current_device)):
    creds = _load_creds()
    result = {}
    for p in _PLATFORMS:
        info = _session_info(p)
        stored = creds.get(p, {})
        result[p] = {
            **info,
            "email": _decode(stored.get("email", "")) or None,
            "has_password": bool(stored.get("password")),
        }
    return CredentialsOut(platforms=result)


@router.post("")
async def save_credentials(
    body: CredentialUpdateRequest,
    _device=Depends(get_current_device),
):
    if body.platform not in _PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {body.platform}")
    creds = _load_creds()
    creds[body.platform] = {
        "email":    _encode(body.email),
        "password": _encode(body.password),
    }
    _save_creds(creds)
    return {"ok": True}


@router.post("/{platform}/relogin")
async def trigger_relogin(platform: str, _device=Depends(get_current_device)):
    if platform not in _PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    creds = _load_creds()
    stored = creds.get(platform, {})
    if not stored.get("email") or not stored.get("password"):
        raise HTTPException(
            status_code=422,
            detail=f"No stored credentials for {platform}. Save email + password first.",
        )

    email    = _decode(stored["email"])
    password = _decode(stored["password"])

    try:
        from src.tasks.auth_tasks import relogin_platform
        task = relogin_platform.delay(platform=platform, email=email, password=password)
        return {"ok": True, "task_id": task.id}
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Re-login task could not be queued. Ensure Celery worker is running.",
        )
