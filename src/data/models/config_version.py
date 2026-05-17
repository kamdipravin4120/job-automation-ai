from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class ConfigVersion(Base):
    __tablename__ = "config_versions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(String(128))
    diff_patch: Mapped[str] = mapped_column(Text)
    rolled_back: Mapped[bool] = mapped_column(Boolean, default=False)
