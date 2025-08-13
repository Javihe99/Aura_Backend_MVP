import pytest
import sys
import os

# Add the parent directory to the path so that the app module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_get_health():
    """Test the health endpoint returns correct status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_get_items():
    """Test the items endpoint returns the expected list of items."""
    response = client.get("/items")
    assert response.status_code == 200
    expected_items = [
        {"id": 1, "name": "Alpha", "price": 10.99},
        {"id": 2, "name": "Beta", "price": 12.50},
        {"id": 3, "name": "Gamma", "price": 7.25},
    ]
    assert response.json() == expected_items
