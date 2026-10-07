from fastapi import status


def test_mixed_batch_with_invalid_recipients(client):
    """
    Test that invalid recipient records fail independently without stopping
    valid certificates in the same batch from being successfully generated.
    """
    payload = {
        "event_name": "Avenger Tactical Engineering",
        "issuer_name": "SHIELD Academy",
        "recipients": [
            # Recipient 1: Valid
            {"name": "Tony Stark", "email": "tony@starkindustries.com"},
            # Recipient 2: Blank name (Validation Failure)
            {"name": "   ", "email": "ghost@example.com"},
            # Recipient 3: Malformed email (Validation Failure)
            {"name": "Peter Parker", "email": "definitely-not-an-email"},
            # Recipient 4: Valid
            {"name": "Natasha Romanoff", "email": "natasha@shield.gov"},
        ],
    }

    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_202_ACCEPTED
    job_id = response.json()["job_id"]

    # Retrieve job status
    status_resp = client.get(f"/api/v1/jobs/{job_id}")
    assert status_resp.status_code == status.HTTP_200_OK

    data = status_resp.json()
    assert data["status"] == "PARTIALLY_COMPLETED"
    assert data["total_count"] == 4
    assert data["processed_count"] == 4
    assert data["success_count"] == 2
    assert data["failure_count"] == 2

    # Map results by recipient name or order
    results = {r["recipient_name"]: r for r in data["recipients"]}

    # Verify Tony Stark succeeded
    assert results["Tony Stark"]["status"] == "SUCCESS"
    assert results["Tony Stark"]["download_url"] is not None
    assert results["Tony Stark"]["error_message"] is None

    # Verify Natasha Romanoff succeeded
    assert results["Natasha Romanoff"]["status"] == "SUCCESS"
    assert results["Natasha Romanoff"]["download_url"] is not None
    assert results["Natasha Romanoff"]["error_message"] is None

    # Verify Blank name failed with clear validation message
    blank_item = [r for r in data["recipients"] if not r["recipient_name"]][0]
    assert blank_item["status"] == "FAILED"
    assert "name is required" in blank_item["error_message"].lower()

    # Verify Invalid email failed with clear validation message
    assert results["Peter Parker"]["status"] == "FAILED"
    assert "invalid email" in results["Peter Parker"]["error_message"].lower()


def test_generator_runtime_failure_isolation(client):
    """
    Test that an unexpected generation failure on one certificate does not
    affect subsequent certificates in the queue.
    """
    payload = {
        "event_name": "Quantum Computing Fundamentals",
        "recipients": [
            {"name": "Steve Rogers", "email": "steve@example.com"},
            {"name": "Loki Laufeyson", "email": "loki@example.com", "custom_attributes": {"simulate_error": True}},
            {"name": "Thor Odinson", "email": "thor@example.com"},
        ],
    }

    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_202_ACCEPTED
    job_id = response.json()["job_id"]

    status_resp = client.get(f"/api/v1/jobs/{job_id}")
    data = status_resp.json()

    assert data["status"] == "PARTIALLY_COMPLETED"
    assert data["total_count"] == 3
    assert data["success_count"] == 2
    assert data["failure_count"] == 1

    results = {r["recipient_name"]: r for r in data["recipients"]}
    assert results["Steve Rogers"]["status"] == "SUCCESS"
    assert results["Thor Odinson"]["status"] == "SUCCESS"
    assert results["Loki Laufeyson"]["status"] == "FAILED"
    assert "simulated" in results["Loki Laufeyson"]["error_message"].lower()


def test_all_recipients_fail(client):
    """Test job status when all recipient entries are invalid."""
    payload = {
        "event_name": "Failure Case Study",
        "recipients": [
            {"name": "", "email": "bad1"},
            {"name": "  ", "email": "bad2"},
        ],
    }

    response = client.post("/api/v1/jobs", json=payload)
    job_id = response.json()["job_id"]

    status_resp = client.get(f"/api/v1/jobs/{job_id}")
    data = status_resp.json()

    assert data["status"] == "FAILED"
    assert data["success_count"] == 0
    assert data["failure_count"] == 2
    assert data["zip_download_url"] is None
