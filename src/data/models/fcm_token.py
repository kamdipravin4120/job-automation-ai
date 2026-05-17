import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class FcmToken(Base):
    __tablename__ = "fcm_tokens"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    token: Mapped[str] = mapped_column(Text, unique=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
