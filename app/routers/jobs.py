import io
import re
import zipfile
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import GenerationJob, CertificateRecord, JobStatus, CertificateStatus
from app.schemas import (
    CertificateCreateRequest,
    JobCreateResponse,
    JobDetailResponse,
    RecipientResultResponse,
    JobListResponse,
    JobSummaryResponse,
)
from app.services.job_service import create_job, process_certificate_job

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def sanitize_filename(name: str) -> str:
    """Create a safe filesystem/archive filename from a recipient name."""
    clean = re.sub(r"[^\w\s-]", "", name).strip()
    return re.sub(r"[-\s]+", "_", clean) or "certificate"


@router.post(
    "",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a Bulk Certificate Generation Request",
)
def submit_generation_job(
    request: CertificateCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Accepts a bulk certificate generation request for a list of recipients.
    Validates payload structure, records job and recipients in the database,
    and delegates PDF rendering to a non-blocking asynchronous background worker.

    Returns HTTP 202 (Accepted) immediately with a job ID and status tracking link.
    """
    if len(request.recipients) > settings.MAX_RECIPIENTS_PER_JOB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch size exceeds maximum limit of {settings.MAX_RECIPIENTS_PER_JOB} recipients.",
        )

    job = create_job(db, request)

    # Queue background generation worker
    background_tasks.add_task(process_certificate_job, job.id)

    status_url = f"{settings.BASE_URL}{settings.API_V1_STR}/jobs/{job.id}"

    return JobCreateResponse(
        job_id=job.id,
        status=job.status,
        total_recipients=job.total_count,
        created_at=job.created_at,
        status_url=status_url,
        message="Bulk certificate generation job accepted and processing in background.",
    )


@router.get(
    "/{job_id}",
    response_model=JobDetailResponse,
    summary="Get Job Status and Progress",
)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """
    Query the progress and results of a bulk generation job.
    Provides total, processed, success, and failure counts, along with an
    itemized list of recipient statuses, individual download URLs, or failure error reasons.
    """
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job '{job_id}' not found.",
        )

    recipient_results: List[RecipientResultResponse] = []
    for cert in job.certificates:
        download_url = None
        if cert.status == CertificateStatus.SUCCESS.value:
            download_url = f"{settings.BASE_URL}{settings.API_V1_STR}/certificates/{cert.id}/download"

        recipient_results.append(
            RecipientResultResponse(
                id=cert.id,
                recipient_name=cert.recipient_name,
                recipient_email=cert.recipient_email,
                status=cert.status,
                download_url=download_url,
                error_message=cert.error_message,
            )
        )

    zip_url = None
    if job.success_count > 0:
        zip_url = f"{settings.BASE_URL}{settings.API_V1_STR}/jobs/{job.id}/download-all"

    return JobDetailResponse(
        job_id=job.id,
        event_name=job.event_name,
        issuer_name=job.issuer_name,
        issue_date=job.issue_date,
        certificate_title=job.certificate_title,
        status=job.status,
        total_count=job.total_count,
        processed_count=job.processed_count,
        success_count=job.success_count,
        failure_count=job.failure_count,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        zip_download_url=zip_url,
        recipients=recipient_results,
    )


@router.get(
    "",
    response_model=JobListResponse,
    summary="List All Generation Jobs",
)
def list_jobs(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    Retrieve a paginated list of all bulk generation jobs with summary metrics.
    """
    total = db.query(GenerationJob).count()
    offset = (page - 1) * page_size
    jobs = (
        db.query(GenerationJob)
        .order_by(GenerationJob.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    summaries = [
        JobSummaryResponse(
            job_id=j.id,
            event_name=j.event_name,
            issuer_name=j.issuer_name,
            status=j.status,
            total_count=j.total_count,
            processed_count=j.processed_count,
            success_count=j.success_count,
            failure_count=j.failure_count,
            created_at=j.created_at,
            completed_at=j.completed_at,
            status_url=f"{settings.BASE_URL}{settings.API_V1_STR}/jobs/{j.id}",
        )
        for j in jobs
    ]

    return JobListResponse(
        total_jobs=total,
        page=page,
        page_size=page_size,
        jobs=summaries,
    )


@router.get(
    "/{job_id}/download-all",
    summary="Download All Generated Certificates as a ZIP Archive",
)
def download_all_certificates_zip(job_id: str, db: Session = Depends(get_db)):
    """
    Package all successfully generated certificates for a job into a ZIP archive
    and stream it directly to the client.
    """
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job '{job_id}' not found.",
        )

    successful_certs = (
        db.query(CertificateRecord)
        .filter(
            CertificateRecord.job_id == job_id,
            CertificateRecord.status == CertificateStatus.SUCCESS.value,
        )
        .all()
    )

    if not successful_certs:
        if job.status in [JobStatus.PENDING.value, JobStatus.PROCESSING.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job is still {job.status}. No certificates are ready for download yet.",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No successful certificates were generated for this job.",
        )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for cert in successful_certs:
            if cert.file_path:
                cert_file = settings.STORAGE_DIR / job_id / f"{cert.id}.pdf"
                if cert_file.exists():
                    safe_name = sanitize_filename(cert.recipient_name)
                    arcname = f"{safe_name}_{cert.id[:8]}.pdf"
                    zf.write(cert_file, arcname=arcname)

    zip_buffer.seek(0)
    zip_filename = f"{sanitize_filename(job.event_name)}_{job.id[:8]}_certificates.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )
