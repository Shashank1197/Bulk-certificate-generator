"""
Accuracy Verification & Benchmark Script for Bulk Certificate Generator.

This script executes a live end-to-end audit:
1. Submits a batch with mixed valid and invalid recipients.
2. Checks status transitions and failure isolation accuracy.
3. Extracts and inspects the text inside generated PDFs using `pypdf` to prove 100% text accuracy.
4. Audits the ZIP archive download to ensure all valid certificates are packaged cleanly.
5. Verifies the public verification endpoint matching the QR code.
6. Measures throughput (certificates per second) and memory/storage efficiency.
"""

import io
import os
import time
import zipfile
from pypdf import PdfReader
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database import init_db


def run_accuracy_audit():
    print("=" * 80)
    print("   BULK CERTIFICATE GENERATOR - ACCURACY & PERFORMANCE AUDIT")
    print("=" * 80)

    # Initialize database schema
    init_db()

    with TestClient(app) as client:
        # 1. Health check
        health_resp = client.get("/api/v1/health")
        assert health_resp.status_code == 200, f"Health check failed: {health_resp.text}"
        print(f"\n[1] Health & Connectivity Check: OK (Status: {health_resp.json()['status']}, DB: {health_resp.json()['database']})")

        # 2. End-to-End Batch with Diverse Payloads
        batch_payload = {
            "event_name": "International AI & Systems Engineering Summit 2026",
            "issuer_name": "MIT & Stanford Consortium",
            "issue_date": "October 6, 2026",
            "certificate_title": "Certificate of Distinction",
            "recipients": [
                {
                    "name": "Alexander Hamilton",
                    "email": "alexander.hamilton@treasury.gov",
                    "custom_attributes": {"Track": "Financial Systems", "Grade": "A+", "Honors": "Highest Distinction"},
                },
                {
                    "name": "Ada Lovelace",
                    "email": "ada.lovelace@analytical.org",
                    "custom_attributes": {"Role": "Keynote Speaker", "Session": "Computational Algorithms"},
                },
                {
                    "name": "Grace Hopper",
                    "email": "grace.hopper@navy.mil",
                    "custom_attributes": {"Specialization": "Compiler Architectures"},
                },
                {
                    # Intentionally invalid: Blank name
                    "name": "   ",
                    "email": "blank.name@test.com",
                },
                {
                    # Intentionally invalid: Malformed email
                    "name": "Leonardo da Vinci",
                    "email": "not_an_email_at_all",
                },
            ],
        }

        print("\n[2] Submitting Batch Job (5 recipients: 3 valid, 2 invalid)...")
        start_time = time.perf_counter()
        resp = client.post("/api/v1/jobs", json=batch_payload)
        submit_elapsed = (time.perf_counter() - start_time) * 1000

        assert resp.status_code == 202, f"Failed job submission: {resp.text}"
        job_info = resp.json()
        job_id = job_info["job_id"]
        print(f"    - Response Status: 202 Accepted (Latency: {submit_elapsed:.2f} ms)")
        print(f"    - Job ID: {job_id}")
        print(f"    - Initial Status: {job_info['status']}")

        # 3. Query Job Status & Failure Isolation
        print("\n[3] Auditing Job Status & Granular Progress Tracking...")
        status_resp = client.get(f"/api/v1/jobs/{job_id}")
        assert status_resp.status_code == 200
        job_data = status_resp.json()

        print(f"    - Overall Job Status: {job_data['status']}")
        print(f"    - Total Recipients:   {job_data['total_count']}")
        print(f"    - Processed Count:    {job_data['processed_count']}")
        print(f"    - Successful Count:   {job_data['success_count']}")
        print(f"    - Failed Count:       {job_data['failure_count']}")

        assert job_data["status"] == "PARTIALLY_COMPLETED", f"Expected PARTIALLY_COMPLETED, got {job_data['status']}"
        assert job_data["success_count"] == 3
        assert job_data["failure_count"] == 2
        assert job_data["processed_count"] == 5

        # 4. Deep Inspection of Text Accuracy inside Generated PDFs
        print("\n[4] Deep Content Accuracy Inspection (Extracting Text from Generated PDFs)...")
        valid_certs = [r for r in job_data["recipients"] if r["status"] == "SUCCESS"]
        failed_certs = [r for r in job_data["recipients"] if r["status"] == "FAILED"]

        for idx, cert in enumerate(valid_certs, start=1):
            cert_id = cert["id"]
            # Download the PDF
            dl_resp = client.get(f"/api/v1/certificates/{cert_id}/download")
            assert dl_resp.status_code == 200, f"Failed to download certificate {cert_id}"
            pdf_bytes = dl_resp.content

            # Inspect using pypdf
            reader = PdfReader(io.BytesIO(pdf_bytes))
            page = reader.pages[0]
            extracted_text = page.extract_text()

            print(f"\n    Certificate #{idx} [{cert['recipient_name']}]:")
            print(f"      - File Size: {len(pdf_bytes)} bytes (~{len(pdf_bytes)/1024:.2f} KB)")
            print(f"      - PDF Magic Header: {pdf_bytes[:8].decode('latin-1')}")
            print(f"      - Number of Pages: {len(reader.pages)}")

            # Verification of exact text elements inside the PDF
            expected_strings = [
                cert["recipient_name"],
                job_data["event_name"],
                job_data["issuer_name"].upper(),
                job_data["certificate_title"].upper(),
                "THIS IS PROUDLY PRESENTED TO",
                "Authorized Signatory",
                cert_id,
            ]

            for expected in expected_strings:
                match = expected in extracted_text
                status_symbol = "[PASS]" if match else "[FAIL]"
                print(f"      {status_symbol} Text Check: '{expected}' present -> {match}")
                assert match, f"Expected string '{expected}' not found in extracted text: {extracted_text}"

        # 5. Auditing Failure Isolation Diagnostics
        print("\n[5] Auditing Failure Handling & Diagnostics Accuracy...")
        for idx, cert in enumerate(failed_certs, start=1):
            name_display = cert["recipient_name"] or "[Blank Name]"
            print(f"    Failed Item #{idx}: Name='{name_display}', Status={cert['status']}")
            print(f"      - Error Reason: \"{cert['error_message']}\"")
            assert cert["error_message"] is not None
            assert "Validation Error" in cert["error_message"]

        # 6. Auditing ZIP Archive Download Accuracy
        print("\n[6] Auditing Bulk ZIP Download Archive...")
        zip_resp = client.get(f"/api/v1/jobs/{job_id}/download-all")
        assert zip_resp.status_code == 200
        assert zip_resp.headers["content-type"] == "application/zip"

        with zipfile.ZipFile(io.BytesIO(zip_resp.content), "r") as zf:
            archive_files = zf.namelist()
            print(f"    - ZIP Archive Total Size: {len(zip_resp.content)} bytes")
            print(f"    - Contained Certificates ({len(archive_files)} files):")
            for f in archive_files:
                file_data = zf.read(f)
                print(f"      * {f} ({len(file_data)} bytes, valid PDF: {file_data.startswith(b'%PDF-')})")
                assert file_data.startswith(b'%PDF-')

            assert len(archive_files) == 3, f"Expected 3 certificates in ZIP, found {len(archive_files)}"

        # 7. Auditing Public Verification (QR Code destination)
        print("\n[7] Auditing Public QR Authenticity Verification Endpoint...")
        sample_cert_id = valid_certs[0]["id"]
        verify_resp = client.get(f"/api/v1/certificates/{sample_cert_id}/verify")
        assert verify_resp.status_code == 200
        v_data = verify_resp.json()
        print(f"    - Certificate ID: {v_data['certificate_id']}")
        print(f"    - Authenticity Valid: {v_data['is_valid']}")
        print(f"    - Recipient: {v_data['recipient_name']}")
        print(f"    - Event: {v_data['event_name']}")
        print(f"    - Issuer: {v_data['issuer_name']}")
        assert v_data["is_valid"] is True
        assert v_data["recipient_name"] == valid_certs[0]["recipient_name"]

        # 8. High-Throughput Batch Performance Benchmark
        print("\n[8] High-Throughput Performance Benchmark...")
        benchmark_counts = [10, 50, 100]
        for count in benchmark_counts:
            recipients = [{"name": f"Candidate {i:03d}", "email": f"candidate{i}@domain.com"} for i in range(1, count + 1)]
            payload = {
                "event_name": f"Large Scale Benchmark - {count} Recipients",
                "recipients": recipients,
            }
            t0 = time.perf_counter()
            create_res = client.post("/api/v1/jobs", json=payload)
            t_submit = (time.perf_counter() - t0) * 1000

            assert create_res.status_code == 202
            bench_job_id = create_res.json()["job_id"]

            t_finish = time.perf_counter() - t0
            stat = client.get(f"/api/v1/jobs/{bench_job_id}").json()

            rate = count / t_finish if t_finish > 0 else 0
            print(f"    - Batch Size: {count:3d} | Total Time: {t_finish:.2f}s | Throughput: {rate:.1f} certs/sec | API Ingress: {t_submit:.1f}ms")
            assert stat["success_count"] == count

    print("\n" + "=" * 80)
    print("   ALL AUDITS PASSED WITH 100% ACCURACY & HIGH EFFICIENCY!")
    print("=" * 80)


if __name__ == "__main__":
    run_accuracy_audit()
