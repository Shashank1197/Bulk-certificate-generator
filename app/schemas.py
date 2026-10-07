from typing import Optional, Any, Dict, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class RecipientItemRequest(BaseModel):
    """Individual recipient record within a bulk certificate request."""

    name: Optional[str] = Field(
        default=None,
        description="Full name of the certificate recipient.",
        examples=["Jane Doe"],
    )
    email: Optional[str] = Field(
        default=None,
        description="Email address of the recipient for notification/identification.",
        examples=["jane.doe@example.com"],
    )
    custom_attributes: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata such as grade, score, role, honors.",
        examples=[{"grade": "A+", "hours": "40"}],
    )


class CertificateCreateRequest(BaseModel):
    """Payload to initiate a bulk certificate generation job."""

    event_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the event, workshop, or course.",
        examples=["Advanced Python & FastAPI Masterclass"],
    )
    issuer_name: Optional[str] = Field(
        default="Acme Global Academy",
        max_length=255,
        description="Organization or institution awarding the certificate.",
        examples=["Acme Global Academy"],
    )
    issue_date: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Issue date (e.g. 'October 6, 2026'). If omitted, current date is used.",
        examples=["October 6, 2026"],
    )
    certificate_title: Optional[str] = Field(
        default="Certificate of Completion",
        max_length=255,
        description="Title printed at the head of the certificate.",
        examples=["Certificate of Completion"],
    )
    recipients: List[RecipientItemRequest] = Field(
        ...,
        description="List of recipients to generate certificates for.",
    )

    @field_validator("event_name")
    @classmethod
    def validate_event_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("event_name cannot be blank or whitespace only.")
        return stripped

    @field_validator("recipients")
    @classmethod
    def validate_recipients_non_empty(cls, v: List[RecipientItemRequest]) -> List[RecipientItemRequest]:
        if not v:
            raise ValueError("The recipients list cannot be empty. At least one recipient is required.")
        return v


class JobCreateResponse(BaseModel):
    """Immediate response returned upon successful job submission."""

    job_id: str
    status: str
    total_recipients: int
    created_at: datetime
    status_url: str
    message: str


class RecipientResultResponse(BaseModel):
    """Detailed result status for an individual recipient."""

    id: str
    recipient_name: str
    recipient_email: Optional[str] = None
    status: str
    download_url: Optional[str] = None
    error_message: Optional[str] = None


class JobDetailResponse(BaseModel):
    """Complete status, metrics, and recipient list for a generation job."""

    job_id: str
    event_name: str
    issuer_name: str
    issue_date: str
    certificate_title: str
    status: str
    total_count: int
    processed_count: int
    success_count: int
    failure_count: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    zip_download_url: Optional[str] = None
    recipients: List[RecipientResultResponse]


class JobSummaryResponse(BaseModel):
    """Lightweight summary of a job for paginated listings."""

    job_id: str
    event_name: str
    issuer_name: str
    status: str
    total_count: int
    processed_count: int
    success_count: int
    failure_count: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    status_url: str


class JobListResponse(BaseModel):
    """Paginated list of generation jobs."""

    total_jobs: int
    page: int
    page_size: int
    jobs: List[JobSummaryResponse]


class CertificateDetailResponse(BaseModel):
    """Metadata response for a single generated certificate."""

    certificate_id: str
    job_id: str
    recipient_name: str
    recipient_email: Optional[str] = None
    event_name: str
    issuer_name: str
    issue_date: str
    certificate_title: str
    status: str
    file_size_bytes: Optional[int] = None
    download_url: str
    verification_url: str
    created_at: datetime


class CertificateVerificationResponse(BaseModel):
    """Public verification response for a certificate."""

    certificate_id: str
    is_valid: bool
    recipient_name: str
    event_name: str
    issuer_name: str
    issue_date: str
    certificate_title: str
    issued_at: datetime


class HealthResponse(BaseModel):
    """System health check response."""

    status: str
    database: str
    timestamp: datetime
    version: str
