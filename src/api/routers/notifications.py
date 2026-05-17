from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.deps import get_current_device
from src.api.schemas.notifications import FcmRegisterOut, FcmRegisterRequest, FcmUnregisterOut
from src.data.db import get_sessionmaker
from src.data.repositories.fcm_tokens import FcmTokensRepository

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@router.post("/fcm/register", response_model=FcmRegisterOut)
async def register_fcm_token(
    body: FcmRegisterRequest,
    device=Depends(get_current_device),
    db: AsyncSession = Depends(_get_db),
):
    repo = FcmTokensRepository(db)
    await repo.register(device_id=device.id, token=body.fcm_token)
    await db.commit()
    return FcmRegisterOut(registered=True)


@router.delete("/fcm/{fcm_token}", response_model=FcmUnregisterOut)
async def unregister_fcm_token(
    fcm_token: str,
    _device=Depends(get_current_device),
    db: AsyncSession = Depends(_get_db),
):
    repo = FcmTokensRepository(db)
    deleted = await repo.unregister(token=fcm_token)
    await db.commit()
    return FcmUnregisterOut(unregistered=deleted)
