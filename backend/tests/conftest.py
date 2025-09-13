"""
Test configuration and fixtures for StyleSync segmentation tests.
"""
import pytest
from fastapi.testclient import TestClient

# Import the main app
from main import app


@pytest.fixture
def test_client():
    """Create test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset metrics before each test."""
    try:
        from app.utils.metrics import reset_metrics
        reset_metrics()
    except ImportError:
        # If metrics not available, skip
        pass
