from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.redis_dep import get_redis
from src.api.schemas.auth import (
    ChallengeRequest,
    ChallengeResponse,
    PairRequest,
    ReauthChallengeRequest,
    ReauthRequest,
    TokenResponse,
)
from src.api.services.auth import pair_device, reauth_device, store_challenge, store_reauth_challenge
from src.data.db import get_sessionmaker

router = APIRouter()


async def _get_db() -> AsyncSession:
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@router.post("/challenge", response_model=ChallengeResponse)
async def challenge(body: ChallengeRequest, request: Request, redis=Depends(get_redis)):
    try:
        challenge_hex = await store_challenge(
            redis,
            body.bootstrap_secret,
            ip=request.client.host if request.client else None,
        )
    except ValueError as exc:
        if str(exc) == "rate_limited":
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        raise  # propagate unexpected ValueError as 500 rather than masking as 401
    if not challenge_hex:
        raise HTTPException(status_code=401, detail="Invalid or expired bootstrap secret")
    return ChallengeResponse(challenge=challenge_hex)


@router.post("/pair", response_model=TokenResponse, status_code=201)
async def pair(
    body: PairRequest,
    request: Request,
    redis=Depends(get_redis),
    db: AsyncSession = Depends(_get_db),
):
    try:
        token = await pair_device(
            redis=redis,
            db=db,
            bootstrap_secret=body.bootstrap_secret,
            public_key_pem=body.public_key,
            signature_hex=body.signature,
            pairing_ip=request.client.host if request.client else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    return TokenResponse(token=token)


@router.post("/reauth/challenge", response_model=ChallengeResponse)
async def reauth_challenge(
    body: ReauthChallengeRequest,
    redis=Depends(get_redis),
    db: AsyncSession = Depends(_get_db),
):
    try:
        challenge_hex = await store_reauth_challenge(redis, db, body.device_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    return ChallengeResponse(challenge=challenge_hex)


@router.post("/reauth", response_model=TokenResponse)
async def reauth(
    body: ReauthRequest,
    redis=Depends(get_redis),
    db: AsyncSession = Depends(_get_db),
):
    try:
        token = await reauth_device(
            redis=redis,
            db=db,
            device_id=body.device_id,
            signature_hex=body.signature,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    return TokenResponse(token=token)
