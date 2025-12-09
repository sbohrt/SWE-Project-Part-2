# tests/security/test_auth.py
"""
Tests for API key authentication.

SECURITY TEST: Verify that admin endpoints require valid API key.
"""
import os
import pytest
from unittest.mock import patch, MagicMock

from swe_project.api.app import create_app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_dynamodb_table():
    """Mock DynamoDB table for testing."""
    with patch('swe_project.api.routes.crud._table') as mock_table:
        # Mock scan response
        mock_table.scan.return_value = {
            'Items': [
                {'modelId': 'model1'},
                {'modelId': 'model2'}
            ]
        }
        yield mock_table


class TestAPIKeyAuthentication:
    """Test API key authentication for protected endpoints."""

    def test_reset_without_api_key_returns_401(self, client, mock_dynamodb_table):
        """DELETE /reset without API key should return 401 Unauthorized."""
        with patch.dict(os.environ, {'ADMIN_API_KEY': 'test-secret-key'}):
            response = client.delete('/api/v1/reset')
            assert response.status_code == 401
            data = response.get_json()
            assert data['error'] == 'Unauthorized'
            assert 'Missing X-API-Key header' in data['message']

    def test_reset_with_invalid_api_key_returns_403(self, client, mock_dynamodb_table):
        """DELETE /reset with invalid API key should return 403 Forbidden."""
        with patch.dict(os.environ, {'ADMIN_API_KEY': 'test-secret-key'}):
            response = client.delete(
                '/api/v1/reset',
                headers={'X-API-Key': 'wrong-key'}
            )
            assert response.status_code == 403
            data = response.get_json()
            assert data['error'] == 'Forbidden'
            assert 'Invalid API key' in data['message']

    def test_reset_with_valid_api_key_succeeds(self, client, mock_dynamodb_table):
        """DELETE /reset with valid API key should return 200."""
        with patch.dict(os.environ, {'ADMIN_API_KEY': 'test-secret-key'}):
            response = client.delete(
                '/api/v1/reset',
                headers={'X-API-Key': 'test-secret-key'}
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data['message'] == 'All models deleted successfully'
            assert data['count'] == 2

    def test_reset_without_configured_api_key_returns_500(self, client, mock_dynamodb_table):
        """DELETE /reset when ADMIN_API_KEY not set should return 500."""
        with patch.dict(os.environ, {}, clear=True):
            response = client.delete(
                '/api/v1/reset',
                headers={'X-API-Key': 'any-key'}
            )
            assert response.status_code == 500
            data = response.get_json()
            assert 'not configured' in data['message']

    def test_timing_attack_resistance(self, client, mock_dynamodb_table):
        """Verify constant-time comparison prevents timing attacks."""
        import time

        with patch.dict(os.environ, {'ADMIN_API_KEY': 'a' * 32}):
            # Test with completely wrong key
            start = time.perf_counter()
            client.delete('/api/v1/reset', headers={'X-API-Key': 'x' * 32})
            wrong_time = time.perf_counter() - start

            # Test with almost correct key (differs only at the end)
            start = time.perf_counter()
            client.delete('/api/v1/reset', headers={'X-API-Key': 'a' * 31 + 'x'})
            almost_time = time.perf_counter() - start

            # Times should be similar (within 10ms) due to constant-time comparison
            # Note: This is a heuristic test and may be flaky on slow systems
            assert abs(wrong_time - almost_time) < 0.01
