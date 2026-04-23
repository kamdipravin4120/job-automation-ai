import uuid
from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    public_key: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    paired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Session(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rotates_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
