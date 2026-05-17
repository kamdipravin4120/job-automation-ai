from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.core.deps import get_current_device
from src.api.schemas.integrations import IntegrationOut
from src.data.db import get_sessionmaker
from src.data.repositories.integrations import IntegrationsRepository

router = APIRouter()


async def _get_db():
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@router.get("", response_model=list[IntegrationOut])
async def list_integrations(
    _device=Depends(get_current_device),
    db=Depends(_get_db),
):
    repo = IntegrationsRepository(db)
    return await repo.list_all()
