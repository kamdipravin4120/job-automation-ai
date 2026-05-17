from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.fcm_token import FcmToken


class FcmTokensRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def register(self, *, device_id: uuid.UUID, token: str) -> FcmToken:
        existing = await self._db.scalar(select(FcmToken).where(FcmToken.token == token))
        if existing:
            existing.last_seen_at = datetime.now(timezone.utc)
            existing.device_id = device_id
            return existing
        row = FcmToken(
            device_id=device_id,
            token=token,
            last_seen_at=datetime.now(timezone.utc),
        )
        self._db.add(row)
        await self._db.flush()
        return row

    async def unregister(self, *, token: str) -> bool:
        result = await self._db.execute(delete(FcmToken).where(FcmToken.token == token))
        return result.rowcount > 0

    async def list_by_device(self, device_id: uuid.UUID) -> list[FcmToken]:
        rows = await self._db.scalars(select(FcmToken).where(FcmToken.device_id == device_id))
        return list(rows)

    async def list_all(self) -> list[FcmToken]:
        rows = await self._db.scalars(select(FcmToken))
        return list(rows)
