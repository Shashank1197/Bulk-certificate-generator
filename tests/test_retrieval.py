import io
import zipfile
from fastapi import status


def test_certificate_metadata_and_download(client):
    """Test retrieving certificate metadata and downloading the PDF."""
    # 1. Create a job
    payload = {
        "event_name": "Full Stack Mastery",
        "recipients": [{"name": "Arthur Dent", "email": "arthur@galaxy.org"}],
    }
    create_resp = client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["job_id"]

    job_status = client.get(f"/api/v1/jobs/{job_id}").json()
    cert_id = job_status["recipients"][0]["id"]

    # 2. Retrieve metadata
    meta_resp = client.get(f"/api/v1/certificates/{cert_id}")
    assert meta_resp.status_code == status.HTTP_200_OK
    meta_data = meta_resp.json()
    assert meta_data["certificate_id"] == cert_id
    assert meta_data["recipient_name"] == "Arthur Dent"
    assert meta_data["status"] == "SUCCESS"
    assert meta_data["download_url"] is not None
    assert meta_data["verification_url"] is not None

    # 3. Download the PDF
    dl_resp = client.get(f"/api/v1/certificates/{cert_id}/download")
    assert dl_resp.status_code == status.HTTP_200_OK
    assert "application/pdf" in dl_resp.headers["content-type"]
    assert "Arthur_Dent" in dl_resp.headers.get("content-disposition", "")
    assert dl_resp.content.startswith(b"%PDF-")


def test_certificate_public_verification(client):
    """Test the public certificate authenticity verification endpoint."""
    payload = {
        "event_name": "Cybersecurity Operations",
        "recipients": [{"name": "Elliot Alderson", "email": "elliot@fsociety.org"}],
    }
    create_resp = client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["job_id"]
    cert_id = client.get(f"/api/v1/jobs/{job_id}").json()["recipients"][0]["id"]

    verify_resp = client.get(f"/api/v1/certificates/{cert_id}/verify")
    assert verify_resp.status_code == status.HTTP_200_OK
    v_data = verify_resp.json()
    assert v_data["is_valid"] is True
    assert v_data["recipient_name"] == "Elliot Alderson"
    assert v_data["event_name"] == "Cybersecurity Operations"


def test_download_all_zip_archive(client):
    """Test packaging and streaming all certificates in a job as a ZIP archive."""
    payload = {
        "event_name": "Data Engineering Intensive",
        "recipients": [
            {"name": "Grace Hopper", "email": "grace@navy.mil"},
            {"name": "Ada Lovelace", "email": "ada@analytical.org"},
        ],
    }
    create_resp = client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["job_id"]

    # Download ZIP
    zip_resp = client.get(f"/api/v1/jobs/{job_id}/download-all")
    assert zip_resp.status_code == status.HTTP_200_OK
    assert zip_resp.headers["content-type"] == "application/zip"
    assert "attachment" in zip_resp.headers.get("content-disposition", "")

    # Unpack ZIP in memory and inspect files
    zip_buffer = io.BytesIO(zip_resp.content)
    with zipfile.ZipFile(zip_buffer, "r") as zf:
        namelist = zf.namelist()
        assert len(namelist) == 2
        assert any("Grace_Hopper" in fname for fname in namelist)
        assert any("Ada_Lovelace" in fname for fname in namelist)
        for fname in namelist:
            content = zf.read(fname)
            assert content.startswith(b"%PDF-")


def test_download_nonexistent_certificate_404(client):
    """Test 404 response when downloading non-existent certificate."""
    resp = client.get("/api/v1/certificates/00000000-0000-0000-0000-000000000000/download")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_download_failed_certificate_400(client):
    """Test 400 response when trying to download a certificate that failed generation."""
    payload = {
        "event_name": "Test Event",
        "recipients": [{"name": "", "email": "bad@email.com"}],  # Will fail validation
    }
    create_resp = client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["job_id"]
    cert_id = client.get(f"/api/v1/jobs/{job_id}").json()["recipients"][0]["id"]

    dl_resp = client.get(f"/api/v1/certificates/{cert_id}/download")
    assert dl_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "has not been successfully generated" in dl_resp.json()["detail"].lower()
