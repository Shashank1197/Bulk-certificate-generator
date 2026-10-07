import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"


class CertificateStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


def get_utc_now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


class GenerationJob(Base):
    """Represents a bulk certificate generation job submitted by a client."""

    __tablename__ = "generation_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_name = Column(String(255), nullable=False)
    issuer_name = Column(String(255), nullable=False, default="Acme Global Academy")
    issue_date = Column(String(50), nullable=False)
    certificate_title = Column(String(255), nullable=False, default="Certificate of Completion")

    status = Column(String(30), nullable=False, default=JobStatus.PENDING.value, index=True)
    total_count = Column(Integer, nullable=False, default=0)
    processed_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    certificates = relationship(
        "CertificateRecord",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="CertificateRecord.created_at",
    )


class CertificateRecord(Base):
    """Represents an individual certificate generation item within a bulk job."""

    __tablename__ = "certificates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    recipient_name = Column(String(255), nullable=False)
    recipient_email = Column(String(255), nullable=True)
    custom_attributes = Column(Text, nullable=True)  # JSON-encoded dictionary

    status = Column(String(20), nullable=False, default=CertificateStatus.PENDING.value, index=True)
    file_path = Column(String(512), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    job = relationship("GenerationJob", back_populates="certificates")
