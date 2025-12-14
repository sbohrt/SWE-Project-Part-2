# tests/api/test_enumerate.py
"""
Tests for artifact enumeration endpoint.
"""
import pytest
from unittest.mock import patch

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
    """Mock DynamoDB table with sample data."""
    with patch('swe_project.api.routes.crud._table') as mock_table:
        # Mock scan response with sample artifacts
        mock_table.scan.return_value = {
            'Items': [
                {
                    'modelId': 'model-123',
                    'name': 'bert-base-uncased',
                    'type': 'model',
                    'net_score': 0.85
                },
                {
                    'modelId': 'model-456',
                    'name': 'gpt2',
                    'type': 'model',
                    'net_score': 0.92
                },
                {
                    'modelId': 'dataset-789',
                    'name': 'bookcorpus',
                    'type': 'dataset',
                    'net_score': 0.78
                }
            ]
        }
        yield mock_table


class TestEnumerateEndpoint:
    """Test the POST /artifacts endpoint."""

    def test_enumerate_all_with_wildcard(self, client, mock_dynamodb_table):
        """Wildcard '*' should return all artifacts."""
        response = client.post(
            '/api/v1/artifacts',
            json=[{"name": "*"}],
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 3

        # Check response structure
        for artifact in data:
            assert 'name' in artifact
            assert 'id' in artifact
            assert 'type' in artifact

    def test_enumerate_filter_by_name(self, client, mock_dynamodb_table):
        """Filter by specific name should return matching artifacts."""
        response = client.post(
            '/api/v1/artifacts',
            json=[{"name": "bert-base-uncased"}],
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['name'] == 'bert-base-uncased'

    def test_enumerate_filter_by_type(self, client, mock_dynamodb_table):
        """Filter by type should return only matching types."""
        response = client.post(
            '/api/v1/artifacts',
            json=[{"name": "*", "types": ["model"]}],
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 2  # Only models
        for artifact in data:
            assert artifact['type'] == 'model'

    def test_enumerate_pagination_offset_header(self, client, mock_dynamodb_table):
        """Response should include pagination offset header."""
        response = client.post(
            '/api/v1/artifacts',
            json=[{"name": "*"}],
            content_type='application/json'
        )

        assert response.status_code == 200
        assert 'offset' in response.headers
        # With 3 items and page size 100, next offset should be 3
        assert response.headers['offset'] == '3'

    def test_enumerate_invalid_request_body(self, client, mock_dynamodb_table):
        """Invalid request body should return 400."""
        # Not a list
        response = client.post(
            '/api/v1/artifacts',
            json={"name": "*"},
            content_type='application/json'
        )
        assert response.status_code == 400

        # Empty list
        response = client.post(
            '/api/v1/artifacts',
            json=[],
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_enumerate_with_offset_parameter(self, client, mock_dynamodb_table):
        """Pagination with offset parameter should skip items."""
        # Get page 2 (offset=2, meaning skip first 2 items)
        response = client.post(
            '/api/v1/artifacts?offset=2',
            json=[{"name": "*"}],
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1  # Should have 1 item (3 total - 2 offset)

    def test_enumerate_invalid_offset(self, client, mock_dynamodb_table):
        """Invalid offset parameter should return 400."""
        response = client.post(
            '/api/v1/artifacts?offset=invalid',
            json=[{"name": "*"}],
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'offset' in data['message'].lower()
