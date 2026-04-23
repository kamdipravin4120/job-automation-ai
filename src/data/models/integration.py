from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Integration(Base):
    __tablename__ = "integrations"
    provider: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32))
    credentials_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
