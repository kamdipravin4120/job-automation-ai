import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_jobs_source_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text)
    company: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_band: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    jd_text: Mapped[str] = mapped_column(Text)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="new")
    user_notes: Mapped[str] = mapped_column(Text, default="")


class JobArtifact(Base):
    __tablename__ = "job_artifacts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(32))
    file_path: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(default=1)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
