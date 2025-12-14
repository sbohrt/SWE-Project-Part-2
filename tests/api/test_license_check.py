# tests/api/test_license_check.py
"""
Tests for license compatibility checking endpoint.
"""
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
    """Mock DynamoDB table with sample data."""
    with patch('swe_project.api.routes.license_check._table') as mock_table:
        # Mock get_item response with sample artifact
        def mock_get_item(Key):
            model_id = Key['modelId']
            if model_id == 'model-mit':
                return {
                    'Item': {
                        'modelId': 'model-mit',
                        'name': 'bert-base-uncased',
                        'type': 'model',
                        'license': 'mit',
                        'license_id': 'mit'
                    }
                }
            elif model_id == 'model-apache':
                return {
                    'Item': {
                        'modelId': 'model-apache',
                        'name': 'gpt2',
                        'type': 'model',
                        'license': 'apache-2.0',
                        'license_id': 'apache-2.0'
                    }
                }
            elif model_id == 'model-gpl':
                return {
                    'Item': {
                        'modelId': 'model-gpl',
                        'name': 'some-model',
                        'type': 'model',
                        'license': 'gpl-3.0',
                        'license_id': 'gpl-3.0'
                    }
                }
            else:
                return {}

        mock_table.get_item = mock_get_item
        yield mock_table


@pytest.fixture
def mock_github_api():
    """Mock GitHub API requests."""
    with patch('swe_project.api.routes.license_check.requests.get') as mock_get:
        def mock_response(url, **kwargs):
            response = MagicMock()

            if 'google-research/bert' in url:
                # Apache 2.0 license
                response.status_code = 200
                response.json.return_value = {
                    'license': {
                        'spdx_id': 'Apache-2.0',
                        'name': 'Apache License 2.0'
                    }
                }
            elif 'openai/gpt-2' in url:
                # MIT license
                response.status_code = 200
                response.json.return_value = {
                    'license': {
                        'spdx_id': 'MIT',
                        'name': 'MIT License'
                    }
                }
            elif 'some/gpl-repo' in url:
                # GPL-3.0 license
                response.status_code = 200
                response.json.return_value = {
                    'license': {
                        'spdx_id': 'GPL-3.0',
                        'name': 'GNU General Public License v3.0'
                    }
                }
            elif 'nonexistent/repo' in url:
                response.status_code = 404
                response.json.return_value = {'message': 'Not Found'}
            else:
                # No license
                response.status_code = 200
                response.json.return_value = {
                    'license': None
                }

            return response

        mock_get.side_effect = mock_response
        yield mock_get


class TestLicenseCheckEndpoint:
    """Test the POST /artifact/model/{id}/license-check endpoint."""

    def test_compatible_licenses(self, client, mock_dynamodb_table, mock_github_api):
        """MIT model with Apache-2.0 GitHub repo should be compatible."""
        response = client.post(
            '/api/v1/artifact/model/model-mit/license-check',
            json={'github_url': 'https://github.com/google-research/bert'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data is True  # Compatible

    def test_compatible_apache_mit(self, client, mock_dynamodb_table, mock_github_api):
        """Apache-2.0 model with MIT GitHub repo should be compatible."""
        response = client.post(
            '/api/v1/artifact/model/model-apache/license-check',
            json={'github_url': 'https://github.com/openai/gpt-2'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data is True  # Compatible

    def test_compatible_gpl_mit(self, client, mock_dynamodb_table, mock_github_api):
        """GPL-3.0 model with MIT GitHub repo should be compatible."""
        response = client.post(
            '/api/v1/artifact/model/model-gpl/license-check',
            json={'github_url': 'https://github.com/openai/gpt-2'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data is True  # GPL can use MIT code

    def test_compatible_mit_gpl(self, client, mock_dynamodb_table, mock_github_api):
        """MIT model with GPL GitHub repo is compatible for fine-tuning use case."""
        response = client.post(
            '/api/v1/artifact/model/model-mit/license-check',
            json={'github_url': 'https://github.com/some/gpl-repo'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        # MIT models can use GPL code for fine-tuning (GPL is in MIT's compatibility list)
        assert data is True

    def test_missing_github_url(self, client, mock_dynamodb_table, mock_github_api):
        """Should return 400 when github_url is missing."""
        response = client.post(
            '/api/v1/artifact/model/model-mit/license-check',
            json={},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'github_url' in data['message'].lower()

    def test_invalid_json(self, client, mock_dynamodb_table, mock_github_api):
        """Should return 400 for invalid JSON."""
        response = client.post(
            '/api/v1/artifact/model/model-mit/license-check',
            data='invalid json',
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_model_not_found(self, client, mock_dynamodb_table, mock_github_api):
        """Should return 404 when model doesn't exist."""
        response = client.post(
            '/api/v1/artifact/model/nonexistent-model/license-check',
            json={'github_url': 'https://github.com/google-research/bert'},
            content_type='application/json'
        )

        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
        assert 'not found' in data['message'].lower()

    def test_github_repo_not_found(self, client, mock_dynamodb_table, mock_github_api):
        """Should return 502 when GitHub repo doesn't exist."""
        response = client.post(
            '/api/v1/artifact/model/model-mit/license-check',
            json={'github_url': 'https://github.com/nonexistent/repo'},
            content_type='application/json'
        )

        assert response.status_code == 502
        data = response.get_json()
        assert 'error' in data

    def test_invalid_github_url_format(self, client, mock_dynamodb_table, mock_github_api):
        """Should return 502 for invalid GitHub URL format."""
        response = client.post(
            '/api/v1/artifact/model/model-mit/license-check',
            json={'github_url': 'https://gitlab.com/some/repo'},
            content_type='application/json'
        )

        assert response.status_code == 502
        data = response.get_json()
        assert 'error' in data

    def test_response_is_boolean(self, client, mock_dynamodb_table, mock_github_api):
        """Response should be a boolean value."""
        response = client.post(
            '/api/v1/artifact/model/model-mit/license-check',
            json={'github_url': 'https://github.com/google-research/bert'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, bool)
