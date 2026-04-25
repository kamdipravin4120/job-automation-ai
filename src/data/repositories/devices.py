from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.device import Device


class DevicesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, device_id: uuid.UUID) -> Device | None:
        return await self.session.get(Device, device_id)

    async def create(
        self,
        *,
        public_key: str,
        pairing_ip: str | None,
        name: str = "",
    ) -> Device:
        device = Device(
            public_key=public_key,
            pairing_ip=pairing_ip,
            name=name,
        )
        self.session.add(device)
        await self.session.flush()
        return device

    async def touch(
        self,
        session: AsyncSession,
        device_id: uuid.UUID,
        *,
        ip: str | None,
        user_agent: str | None,
    ) -> None:
        device = await session.get(Device, device_id)
        if device is None:
            return
        device.last_seen_at = datetime.now(UTC)
        device.last_ip = ip
        device.last_user_agent = user_agent
        await session.flush()

    async def revoke(self, session: AsyncSession, device_id: uuid.UUID) -> None:
        device = await session.get(Device, device_id)
        if device is None:
            return
        device.revoked_at = datetime.now(UTC)
        await session.flush()
