import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class SavedSearch(Base):
    __tablename__ = "saved_searches"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keywords: Mapped[str] = mapped_column(String(256))
    location: Mapped[str] = mapped_column(String(256))
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    min_match_score: Mapped[float] = mapped_column(Float, default=0.6)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    run_every_hours: Mapped[int] = mapped_column(Integer, default=24)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
