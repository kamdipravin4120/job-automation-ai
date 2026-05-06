from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.core.deps import get_current_device
from src.api.schemas.gmail import GmailStatusOut, OAuthInitOut, OAuthPollOut, SyncOut
from src.settings import get_settings

router = APIRouter(prefix="/api/v1/gmail", tags=["gmail"])

_pending_oauth: dict[str, object] = {}


def _get_oauth():
    settings = get_settings()
    if not settings.gmail_client_id or not settings.gmail_client_secret:
        raise HTTPException(status_code=503, detail="GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET not configured")
    from src.gmail.oauth import GmailOAuth
    return GmailOAuth(
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret.get_secret_value(),
        token_path=settings.gmail_token_path,
    )


@router.get("/status", response_model=GmailStatusOut)
async def gmail_status(_device=Depends(get_current_device)):
    settings = get_settings()
    if not settings.gmail_client_id:
        return GmailStatusOut(authorized=False)
    from src.gmail.oauth import GmailOAuth
    oauth = GmailOAuth(
        client_id=settings.gmail_client_id,
        client_secret=(settings.gmail_client_secret.get_secret_value() if settings.gmail_client_secret else ""),
        token_path=settings.gmail_token_path,
    )
    return GmailStatusOut(authorized=oauth.is_authorized())


@router.post("/oauth/init", response_model=OAuthInitOut)
async def oauth_init(device=Depends(get_current_device)):
    oauth = _get_oauth()
    code_resp = oauth.init_device_flow()
    _pending_oauth[str(device.id)] = oauth
    return OAuthInitOut(
        user_code=code_resp.user_code,
        verification_url=code_resp.verification_url,
        expires_in=code_resp.expires_in,
    )


@router.get("/oauth/poll", response_model=OAuthPollOut)
async def oauth_poll(device=Depends(get_current_device)):
    oauth = _pending_oauth.get(str(device.id))
    if not oauth:
        raise HTTPException(status_code=400, detail="No pending OAuth flow — call /oauth/init first")
    from src.gmail.oauth import GmailOAuth
    status = oauth.poll_for_token()
    if status == "authorized":
        _pending_oauth.pop(str(device.id), None)
    return OAuthPollOut(status=status)


@router.post("/sync", response_model=SyncOut)
async def gmail_sync(_device=Depends(get_current_device)):
    oauth = _get_oauth()
    if not oauth.is_authorized():
        raise HTTPException(status_code=403, detail="Gmail not authorized — complete OAuth flow first")
    from anthropic import Anthropic
    from src.gmail.classifier import EmailStatus, classify_email
    from src.gmail.client import GmailClient
    settings = get_settings()
    creds = oauth.get_credentials()
    client = GmailClient(credentials=creds)
    messages = client.list_unread(max_results=50)
    anthropic = Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
    classified: dict[str, int] = {s.value: 0 for s in EmailStatus}
    for msg in messages:
        status = classify_email(msg.subject, msg.body, anthropic)
        classified[status.value] += 1
    return SyncOut(processed=len(messages), classified=classified)
