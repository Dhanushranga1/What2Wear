"""
Test health endpoint for StyleSync segmentation.
"""
import pytest
from fastapi.testclient import TestClient


def test_health_check_when_available(test_client):
    """Test health check when StyleSync is available."""
    response = test_client.get("/stylesync/healthz")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check required fields
    assert "ok" in data
    assert "version" in data
    assert "service" in data
    assert data["service"] == "stylesync-segmentation"


def test_health_check_when_unavailable():
    """Test health check when StyleSync is unavailable."""
    # This would be tested in a separate environment without dependencies
    pass
