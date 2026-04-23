import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class SelectorOverride(Base):
    __tablename__ = "selector_overrides"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(32))
    key_path: Mapped[str] = mapped_column(Text)
    selector: Mapped[str] = mapped_column(Text)
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    proposed_by: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    dom_snapshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
