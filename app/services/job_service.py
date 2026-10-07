import re
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

from sqlalchemy.orm import Session
from app.config import settings
from app.database import SessionLocal
from app.models import GenerationJob, CertificateRecord, JobStatus, CertificateStatus, get_utc_now
from app.schemas import CertificateCreateRequest, RecipientItemRequest
from app.services.certificate_generator import generate_certificate_pdf

logger = logging.getLogger(__name__)
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_recipient(item: RecipientItemRequest) -> Tuple[bool, Optional[str]]:
    """
    Validate individual recipient data.
    Returns (is_valid, error_message).
    """
    if not item.name or not item.name.strip():
        return False, "Validation Error: Recipient name is required and cannot be empty."

    if len(item.name.strip()) > 255:
        return False, "Validation Error: Recipient name exceeds maximum allowed length of 255 characters."

    if item.email is not None and item.email.strip():
        email_clean = item.email.strip()
        if not EMAIL_REGEX.match(email_clean):
            return False, f"Validation Error: Invalid email address format '{email_clean}'."

    return True, None


def create_job(db: Session, request: CertificateCreateRequest) -> GenerationJob:
    """
    Persist a new GenerationJob and associated CertificateRecord placeholders in the database.
    """
    now = get_utc_now()
    issue_date = request.issue_date or now.strftime("%B %d, %Y")

    job = GenerationJob(
        event_name=request.event_name,
        issuer_name=request.issuer_name or "Acme Global Academy",
        issue_date=issue_date,
        certificate_title=request.certificate_title or "Certificate of Completion",
        status=JobStatus.PENDING.value,
        total_count=len(request.recipients),
        processed_count=0,
        success_count=0,
        failure_count=0,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.flush()  # Populates job.id

    for item in request.recipients:
        cert_record = CertificateRecord(
            job_id=job.id,
            recipient_name=(item.name or "").strip(),
            recipient_email=item.email.strip() if item.email else None,
            custom_attributes=json.dumps(item.custom_attributes) if item.custom_attributes else None,
            status=CertificateStatus.PENDING.value,
            created_at=now,
        )
        db.add(cert_record)

    db.commit()
    db.refresh(job)
    return job


def process_certificate_job(job_id: str) -> None:
    """
    Background worker that iterates through each recipient in a job, validates the data,
    renders the vector PDF certificate, handles partial failures without stopping valid items,
    and updates job status atomically.
    """
    db: Session = SessionLocal()
    try:
        job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found for background execution.")
            return

        job.status = JobStatus.PROCESSING.value
        job.updated_at = get_utc_now()
        db.commit()

        job_storage_dir = settings.STORAGE_DIR / job_id
        job_storage_dir.mkdir(parents=True, exist_ok=True)

        for cert in job.certificates:
            recipient_item = RecipientItemRequest(
                name=cert.recipient_name,
                email=cert.recipient_email,
                custom_attributes=json.loads(cert.custom_attributes) if cert.custom_attributes else None,
            )

            # 1. Validation Step
            is_valid, validation_err = validate_recipient(recipient_item)
            if not is_valid:
                cert.status = CertificateStatus.FAILED.value
                cert.error_message = validation_err
                cert.completed_at = get_utc_now()
                job.failure_count += 1
                job.processed_count += 1
                job.updated_at = get_utc_now()
                db.commit()
                continue

            # Check if simulation trigger is requested (for testing individual failure handling)
            custom_attrs = recipient_item.custom_attributes or {}
            if custom_attrs.get("simulate_error") is True:
                cert.status = CertificateStatus.FAILED.value
                cert.error_message = "Generation Error: Simulated rendering failure for testing."
                cert.completed_at = get_utc_now()
                job.failure_count += 1
                job.processed_count += 1
                job.updated_at = get_utc_now()
                db.commit()
                continue

            # 2. PDF Generation Step
            output_pdf_path = str(job_storage_dir / f"{cert.id}.pdf")
            verify_url = f"{settings.BASE_URL}{settings.API_V1_STR}/certificates/{cert.id}/verify"

            try:
                saved_path, file_size = generate_certificate_pdf(
                    certificate_id=cert.id,
                    recipient_name=cert.recipient_name,
                    event_name=job.event_name,
                    issuer_name=job.issuer_name,
                    issue_date=job.issue_date,
                    certificate_title=job.certificate_title,
                    custom_attributes=custom_attrs,
                    output_path=output_pdf_path,
                    verification_url=verify_url,
                )

                cert.status = CertificateStatus.SUCCESS.value
                cert.file_path = saved_path
                cert.file_size_bytes = file_size
                cert.error_message = None
                cert.completed_at = get_utc_now()
                job.success_count += 1
            except Exception as exc:
                logger.exception(f"Failed generating certificate for {cert.recipient_name}: {exc}")
                cert.status = CertificateStatus.FAILED.value
                cert.error_message = f"Generation Error: {str(exc)}"
                cert.completed_at = get_utc_now()
                job.failure_count += 1

            job.processed_count += 1
            job.updated_at = get_utc_now()
            db.commit()

        # 3. Final Job Status Determination
        if job.success_count == job.total_count:
            job.status = JobStatus.COMPLETED.value
        elif job.success_count > 0:
            job.status = JobStatus.PARTIALLY_COMPLETED.value
        else:
            job.status = JobStatus.FAILED.value

        job.completed_at = get_utc_now()
        job.updated_at = get_utc_now()
        db.commit()

    except Exception as exc:
        logger.exception(f"Unexpected fatal error while processing job {job_id}: {exc}")
        try:
            job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.completed_at = get_utc_now()
                job.updated_at = get_utc_now()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
