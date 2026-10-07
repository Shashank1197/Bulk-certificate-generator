import pytest
from fastapi import status
from app.config import settings
from app.schemas import RecipientItemRequest
from app.services.job_service import validate_recipient


def test_missing_event_name(client):
    """Test payload validation when event_name is omitted."""
    payload = {
        "recipients": [{"name": "Bruce Wayne", "email": "bruce@wayne.com"}]
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_blank_event_name(client):
    """Test payload validation when event_name is whitespace."""
    payload = {
        "event_name": "   ",
        "recipients": [{"name": "Bruce Wayne", "email": "bruce@wayne.com"}]
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_empty_recipients_list(client):
    """Test payload validation when recipients array is empty."""
    payload = {
        "event_name": "AI Systems Workshop",
        "recipients": []
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_exceeding_max_recipients_limit(client, monkeypatch):
    """Test batch size limit constraint."""
    monkeypatch.setattr(settings, "MAX_RECIPIENTS_PER_JOB", 2)
    payload = {
        "event_name": "Big Event",
        "recipients": [
            {"name": "User 1"},
            {"name": "User 2"},
            {"name": "User 3"},
        ]
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "exceeds maximum limit" in response.json()["detail"].lower()


def test_unit_validate_recipient():
    """Unit tests for recipient data validation rules."""
    # Blank name
    is_valid, err = validate_recipient(RecipientItemRequest(name=""))
    assert not is_valid
    assert "name is required" in err.lower()

    # None name
    is_valid, err = validate_recipient(RecipientItemRequest(name=None))
    assert not is_valid
    assert "name is required" in err.lower()

    # Overlong name
    is_valid, err = validate_recipient(RecipientItemRequest(name="A" * 300))
    assert not is_valid
    assert "exceeds maximum allowed length" in err.lower()

    # Invalid email
    is_valid, err = validate_recipient(RecipientItemRequest(name="Valid Name", email="not-an-email"))
    assert not is_valid
    assert "invalid email" in err.lower()

    # Valid name & valid email
    is_valid, err = validate_recipient(RecipientItemRequest(name="Valid Name", email="user@domain.com"))
    assert is_valid
    assert err is None

    # Valid name with no email (optional)
    is_valid, err = validate_recipient(RecipientItemRequest(name="Valid Name", email=None))
    assert is_valid
    assert err is None
