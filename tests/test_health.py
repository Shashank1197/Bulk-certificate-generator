from fastapi import status


def test_health_check_endpoint(client):
    """Test health check endpoint reporting service and database readiness."""
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "version" in data
    assert "timestamp" in data
