from fastapi import status


def test_create_generation_job_success(client):
    """Test successful submission of a bulk certificate generation job."""
    payload = {
        "event_name": "Cloud Native Architecture Bootcamp",
        "issuer_name": "DevOps Global Academy",
        "issue_date": "October 6, 2026",
        "certificate_title": "Certificate of Excellence",
        "recipients": [
            {"name": "Alice Morgan", "email": "alice@example.com", "custom_attributes": {"score": "98%"}},
            {"name": "Bob Vance", "email": "bob@example.com", "custom_attributes": {"score": "92%"}},
        ],
    }

    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_202_ACCEPTED

    data = response.json()
    assert "job_id" in data
    assert data["total_recipients"] == 2
    assert "status_url" in data
    assert data["job_id"] in data["status_url"]

    # Since TestClient executes background tasks, check that job is completed
    status_response = client.get(f"/api/v1/jobs/{data['job_id']}")
    assert status_response.status_code == status.HTTP_200_OK

    job_data = status_response.json()
    assert job_data["job_id"] == data["job_id"]
    assert job_data["status"] == "COMPLETED"
    assert job_data["total_count"] == 2
    assert job_data["processed_count"] == 2
    assert job_data["success_count"] == 2
    assert job_data["failure_count"] == 0
    assert len(job_data["recipients"]) == 2
    assert job_data["zip_download_url"] is not None


def test_alias_certificate_generate_endpoint(client):
    """Test the alias endpoint POST /api/v1/certificates/generate."""
    payload = {
        "event_name": "FastAPI Masterclass",
        "recipients": [
            {"name": "Diana Prince", "email": "diana@example.com"},
        ],
    }

    response = client.post("/api/v1/certificates/generate", json=payload)
    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()
    assert data["total_recipients"] == 1

    status_resp = client.get(f"/api/v1/jobs/{data['job_id']}")
    assert status_resp.status_code == status.HTTP_200_OK
    assert status_resp.json()["status"] == "COMPLETED"


def test_get_nonexistent_job(client):
    """Test 404 response for non-existent job ID."""
    response = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


def test_list_jobs_pagination(client):
    """Test listing jobs with pagination."""
    # Create two jobs
    for i in range(2):
        client.post(
            "/api/v1/jobs",
            json={
                "event_name": f"Event Batch {i}",
                "recipients": [{"name": f"Recipient {i}", "email": f"user{i}@example.com"}],
            },
        )

    response = client.get("/api/v1/jobs?page=1&page_size=10")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_jobs"] >= 2
    assert len(data["jobs"]) >= 2
    assert "job_id" in data["jobs"][0]
