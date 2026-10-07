import os
from pathlib import Path
from app.services.certificate_generator import generate_certificate_pdf


def test_generate_certificate_pdf_creates_valid_pdf(temp_storage):
    """Test that certificate PDF generator produces a valid vector PDF file."""
    output_path = str(temp_storage / "unit_test_cert.pdf")
    verify_url = "http://localhost:8000/api/v1/certificates/test-uuid/verify"

    saved_path, file_size = generate_certificate_pdf(
        certificate_id="CERT-TEST-12345",
        recipient_name="Clark Kent",
        event_name="Journalism & Data Engineering Summit",
        issuer_name="Metropolis Daily Academy",
        issue_date="October 6, 2026",
        certificate_title="Certificate of Achievement",
        custom_attributes={"Track": "Investigative Analysis", "Honor": "Summa Cum Laude"},
        output_path=output_path,
        verification_url=verify_url,
    )

    assert os.path.exists(saved_path)
    assert file_size > 0
    assert file_size == os.path.getsize(saved_path)

    # Verify standard PDF magic number header
    with open(saved_path, "rb") as f:
        header = f.read(5)
        assert header.startswith(b"%PDF-")


def test_generate_certificate_pdf_nested_directory_creation(temp_storage):
    """Test that nested parent directories are created on-the-fly."""
    nested_path = str(temp_storage / "nested" / "subfolder" / "deep_cert.pdf")
    saved_path, file_size = generate_certificate_pdf(
        certificate_id="CERT-NESTED-999",
        recipient_name="Bruce Banner",
        event_name="Gamma Radiation Physics",
        issuer_name="Culver University",
        issue_date="October 6, 2026",
        certificate_title="Certificate of Participation",
        custom_attributes=None,
        output_path=nested_path,
        verification_url="http://localhost:8000/verify/test",
    )

    assert os.path.exists(saved_path)
    assert file_size > 1000
