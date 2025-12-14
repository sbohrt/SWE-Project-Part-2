# tests/api/test_cost.py
"""
Tests for artifact cost calculation endpoint.
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
    with patch('swe_project.api.routes.cost._table') as mock_table:
        # Mock get_item response with sample artifact
        def mock_get_item(Key):
            model_id = Key['modelId']
            if model_id == 'model-123':
                return {
                    'Item': {
                        'modelId': 'model-123',
                        'name': 'bert-base-uncased',
                        'type': 'model',
                        'size_score': {
                            'raspberry_pi': 0.2,
                            'jetson_nano': 0.4,
                            'desktop_pc': 0.8,
                            'aws_server': 0.9
                        }
                    }
                }
            elif model_id == 'model-with-size':
                return {
                    'Item': {
                        'modelId': 'model-with-size',
                        'name': 'gpt2',
                        'type': 'model',
                        'size_mb': 548.5
                    }
                }
            else:
                return {}

        mock_table.get_item = mock_get_item
        yield mock_table


class TestCostEndpoint:
    """Test the GET /artifact/{artifact_type}/{id}/cost endpoint."""

    def test_cost_without_dependencies(self, client, mock_dynamodb_table):
        """Should return total_cost only when dependency=false."""
        response = client.get('/api/v1/artifact/model/model-123/cost')

        assert response.status_code == 200
        data = response.get_json()

        assert 'model-123' in data
        assert 'total_cost' in data['model-123']
        assert 'standalone_cost' not in data['model-123']  # Not included when dependency=false

    def test_cost_with_dependencies(self, client, mock_dynamodb_table):
        """Should return standalone_cost and total_cost when dependency=true."""
        response = client.get('/api/v1/artifact/model/model-123/cost?dependency=true')

        assert response.status_code == 200
        data = response.get_json()

        assert 'model-123' in data
        assert 'standalone_cost' in data['model-123']
        assert 'total_cost' in data['model-123']

    def test_cost_with_explicit_size(self, client, mock_dynamodb_table):
        """Should use explicit size_mb when available."""
        response = client.get('/api/v1/artifact/model/model-with-size/cost')

        assert response.status_code == 200
        data = response.get_json()

        assert 'model-with-size' in data
        assert data['model-with-size']['total_cost'] == 548.5

    def test_cost_invalid_artifact_type(self, client, mock_dynamodb_table):
        """Should return 400 for invalid artifact type."""
        response = client.get('/api/v1/artifact/invalid-type/model-123/cost')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'Invalid artifact_type' in data['message']

    def test_cost_artifact_not_found(self, client, mock_dynamodb_table):
        """Should return 404 for non-existent artifact."""
        response = client.get('/api/v1/artifact/model/nonexistent-id/cost')

        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
        assert 'not found' in data['message'].lower()

    def test_cost_for_dataset_type(self, client, mock_dynamodb_table):
        """Should work for dataset artifact type."""
        response = client.get('/api/v1/artifact/dataset/model-123/cost')

        assert response.status_code == 200
        data = response.get_json()
        assert 'model-123' in data

    def test_cost_for_code_type(self, client, mock_dynamodb_table):
        """Should work for code artifact type."""
        response = client.get('/api/v1/artifact/code/model-123/cost')

        assert response.status_code == 200
        data = response.get_json()
        assert 'model-123' in data

    def test_cost_values_are_numbers(self, client, mock_dynamodb_table):
        """Cost values should be numeric."""
        response = client.get('/api/v1/artifact/model/model-123/cost?dependency=true')

        assert response.status_code == 200
        data = response.get_json()

        assert isinstance(data['model-123']['standalone_cost'], (int, float))
        assert isinstance(data['model-123']['total_cost'], (int, float))
        assert data['model-123']['standalone_cost'] > 0
        assert data['model-123']['total_cost'] > 0
