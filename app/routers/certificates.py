import re
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import CertificateRecord, CertificateStatus
from app.schemas import CertificateDetailResponse, CertificateVerificationResponse

router = APIRouter(prefix="/certificates", tags=["Certificates"])


def sanitize_filename(name: str) -> str:
    """Create a safe download filename."""
    clean = re.sub(r"[^\w\s-]", "", name).strip()
    return re.sub(r"[-\s]+", "_", clean) or "certificate"


@router.get(
    "/{certificate_id}",
    response_model=CertificateDetailResponse,
    summary="Get Certificate Metadata",
)
def get_certificate_metadata(certificate_id: str, db: Session = Depends(get_db)):
    """
    Retrieve comprehensive metadata for an individual certificate, including
    recipient name, event name, issue date, generation status, and links for download and verification.
    """
    cert = db.query(CertificateRecord).filter(CertificateRecord.id == certificate_id).first()
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate '{certificate_id}' not found.",
        )

    download_url = f"{settings.BASE_URL}{settings.API_V1_STR}/certificates/{cert.id}/download"
    verification_url = f"{settings.BASE_URL}{settings.API_V1_STR}/certificates/{cert.id}/verify"

    return CertificateDetailResponse(
        certificate_id=cert.id,
        job_id=cert.job_id,
        recipient_name=cert.recipient_name,
        recipient_email=cert.recipient_email,
        event_name=cert.job.event_name,
        issuer_name=cert.job.issuer_name,
        issue_date=cert.job.issue_date,
        certificate_title=cert.job.certificate_title,
        status=cert.status,
        file_size_bytes=cert.file_size_bytes,
        download_url=download_url,
        verification_url=verification_url,
        created_at=cert.created_at,
    )


@router.get(
    "/{certificate_id}/download",
    summary="Download Individual Certificate PDF",
)
def download_certificate_pdf(certificate_id: str, db: Session = Depends(get_db)):
    """
    Stream the generated PDF certificate directly to the client browser or downloader.
    """
    cert = db.query(CertificateRecord).filter(CertificateRecord.id == certificate_id).first()
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate '{certificate_id}' not found.",
        )

    if cert.status != CertificateStatus.SUCCESS.value or not cert.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Certificate has not been successfully generated. Current status: '{cert.status}'. Reason: {cert.error_message}",
        )

    file_path = Path(cert.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The generated certificate file was not found on the server storage.",
        )

    safe_name = sanitize_filename(cert.recipient_name)
    download_filename = f"{safe_name}_{cert.id[:8]}.pdf"

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=download_filename,
    )


@router.get(
    "/{certificate_id}/verify",
    response_model=CertificateVerificationResponse,
    summary="Verify Certificate Authenticity",
)
def verify_certificate(certificate_id: str, db: Session = Depends(get_db)):
    """
    Public authenticity verification endpoint referenced by the certificate's embedded QR code.
    Allows students, employers, and verifiers to confirm certificate legitimacy.
    """
    cert = db.query(CertificateRecord).filter(CertificateRecord.id == certificate_id).first()
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate record not found. This certificate may be invalid or unissued.",
        )

    if cert.status != CertificateStatus.SUCCESS.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This certificate was not successfully issued.",
        )

    return CertificateVerificationResponse(
        certificate_id=cert.id,
        is_valid=True,
        recipient_name=cert.recipient_name,
        event_name=cert.job.event_name,
        issuer_name=cert.job.issuer_name,
        issue_date=cert.job.issue_date,
        certificate_title=cert.job.certificate_title,
        issued_at=cert.created_at,
    )
