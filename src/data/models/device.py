import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text, TypeDecorator, func
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class InetString(TypeDecorator):
    """INET column that always returns a plain str (not IPv4Address/IPv6Address)."""

    impl = INET
    cache_ok = True

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), default="")
    public_key: Mapped[str] = mapped_column(Text, unique=True)
    paired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    pairing_ip: Mapped[str | None] = mapped_column(InetString, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_ip: Mapped[str | None] = mapped_column(InetString, nullable=True)
    last_user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
