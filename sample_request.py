"""
Sample script to demonstrate submitting a bulk certificate generation job,
monitoring its real-time progress, and retrieving the results.
"""

import time
import requests

BASE_URL = "http://127.0.0.1:8000"


def run_demo():
    print("=" * 60)
    print("Bulk Certificate Generator - API Demo")
    print("=" * 60)

    # 1. Check health
    try:
        health_resp = requests.get(f"{BASE_URL}/api/v1/health")
        print(f"[1] Health Check: {health_resp.status_code} -> {health_resp.json()}")
    except requests.exceptions.ConnectionError:
        print(f"[!] Server is not running at {BASE_URL}. Start it with 'python run.py' first.")
        return

    # 2. Submit Bulk Job
    payload = {
        "event_name": "Full-Stack System Engineering Bootcamp 2026",
        "issuer_name": "Apex Technology Institute",
        "issue_date": "October 6, 2026",
        "certificate_title": "Certificate of Excellence",
        "recipients": [
            {
                "name": "Sarah Connor",
                "email": "sarah.connor@example.com",
                "custom_attributes": {"Track": "DevOps", "Grade": "Distinction"},
            },
            {
                "name": "John Connor",
                "email": "john.connor@example.com",
                "custom_attributes": {"Track": "Cybersecurity", "Grade": "Honors"},
            },
            {
                "name": "Kyle Reese",
                "email": "kyle.reese@example.com",
                "custom_attributes": {"Track": "Cloud Architecture", "Grade": "Merit"},
            },
            {
                # Deliberate validation failure test item to demonstrate partial failure isolation
                "name": "",
                "email": "invalid-person@example.com",
            },
        ],
    }

    print("\n[2] Submitting bulk generation job...")
    create_resp = requests.post(f"{BASE_URL}/api/v1/jobs", json=payload)
    if create_resp.status_code != 202:
        print(f"Error submitting job: {create_resp.status_code} {create_resp.text}")
        return

    job_data = create_resp.json()
    job_id = job_data["job_id"]
    print(f"    Job Accepted (HTTP 202): ID = {job_id}")
    print(f"    Total Recipients: {job_data['total_recipients']}")
    print(f"    Status URL: {job_data['status_url']}")

    # 3. Poll for progress
    print("\n[3] Polling job status...")
    max_retries = 10
    final_status = None
    for attempt in range(max_retries):
        time.sleep(1)
        status_resp = requests.get(f"{BASE_URL}/api/v1/jobs/{job_id}")
        data = status_resp.json()
        status = data["status"]
        processed = data["processed_count"]
        total = data["total_count"]
        print(f"    Attempt {attempt + 1}: Status = {status} ({processed}/{total} processed)")
        if status in ["COMPLETED", "PARTIALLY_COMPLETED", "FAILED"]:
            final_status = data
            break

    if not final_status:
        print("Polling timed out.")
        return

    print("\n[4] Job Execution Summary:")
    print(f"    Status: {final_status['status']}")
    print(f"    Success Count: {final_status['success_count']}")
    print(f"    Failure Count: {final_status['failure_count']}")
    if final_status.get("zip_download_url"):
        print(f"    ZIP Archive Download URL: {final_status['zip_download_url']}")

    print("\n[5] Itemized Recipient Breakdown:")
    for r in final_status["recipients"]:
        name = r["recipient_name"] or "[Blank Name]"
        print(f"    - {name}: Status = {r['status']}")
        if r["download_url"]:
            print(f"      Download URL: {r['download_url']}")
        if r["error_message"]:
            print(f"      Failure Reason: {r['error_message']}")

    print("\nDemo completed successfully!")


if __name__ == "__main__":
    run_demo()
