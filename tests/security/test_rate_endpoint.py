# tests/security/test_rate_endpoint.py
"""
Tests for Rate endpoint security.

SECURITY TEST: Verify rate endpoint validates URLs and prevents SSRF.
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


class TestRateEndpointSecurity:
    """Test security controls on the /rate endpoint."""

    def test_missing_url_returns_400(self, client):
        """POST /rate without URL should return 400."""
        response = client.post(
            '/api/v1/rate',
            json={}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'BadRequest'
        assert 'Missing required field: url' in data['message']

    def test_empty_body_returns_400(self, client):
        """POST /rate with empty body should return 400."""
        response = client.post(
            '/api/v1/rate',
            data='',
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'BadRequest'

    def test_localhost_url_rejected(self, client):
        """POST /rate with localhost URL should be rejected."""
        urls = [
            "http://localhost:8080/api",
            "http://127.0.0.1/secret",
            "http://0.0.0.0/internal"
        ]
        for url in urls:
            response = client.post(
                '/api/v1/rate',
                json={'url': url}
            )
            assert response.status_code == 400, f"URL {url} should be rejected"
            data = response.get_json()
            assert data['error'] == 'BadRequest'
            assert 'Invalid URL' in data['message']
            assert 'Private addresses' in data['message']

    def test_private_ip_rejected(self, client):
        """POST /rate with private IP should be rejected."""
        urls = [
            "http://10.0.0.1/api",
            "http://192.168.1.1/data",
            "http://169.254.169.254/latest/meta-data/"  # AWS metadata
        ]
        for url in urls:
            response = client.post(
                '/api/v1/rate',
                json={'url': url}
            )
            assert response.status_code == 400, f"Private IP {url} should be rejected"
            data = response.get_json()
            assert 'Private addresses' in data['message']

    def test_non_whitelisted_domain_rejected(self, client):
        """POST /rate with non-whitelisted domain should be rejected."""
        urls = [
            "https://evil.com/payload",
            "https://attacker.net/malware",
            "http://internal-server.local/api"
        ]
        for url in urls:
            response = client.post(
                '/api/v1/rate',
                json={'url': url}
            )
            assert response.status_code == 400, f"URL {url} should be rejected"
            data = response.get_json()
            assert 'Domain not allowed' in data['message']

    def test_non_http_scheme_rejected(self, client):
        """POST /rate with non-HTTP scheme should be rejected."""
        urls = [
            "file:///etc/passwd",
            "ftp://huggingface.co/model",
            "javascript:alert(1)"
        ]
        for url in urls:
            response = client.post(
                '/api/v1/rate',
                json={'url': url}
            )
            assert response.status_code == 400, f"URL {url} should be rejected"
            data = response.get_json()
            assert 'HTTP or HTTPS' in data['message']

    @patch('swe_project.api.routes.rate.score_single_model')
    def test_valid_huggingface_url_accepted(self, mock_score, client):
        """POST /rate with valid Hugging Face URL should be accepted."""
        # Mock the score_single_model function
        mock_score.return_value = {
            'url': 'https://huggingface.co/bert-base-uncased',
            'net_score': 0.85,
            'name': 'bert-base-uncased'
        }

        response = client.post(
            '/api/v1/rate',
            json={'url': 'https://huggingface.co/bert-base-uncased'}
        )
        assert response.status_code == 200
        mock_score.assert_called_once_with('https://huggingface.co/bert-base-uncased')

    @patch('swe_project.api.routes.rate.score_single_model')
    def test_valid_github_url_accepted(self, mock_score, client):
        """POST /rate with valid GitHub URL should be accepted."""
        mock_score.return_value = {
            'url': 'https://github.com/user/repo',
            'net_score': 0.75,
            'name': 'repo'
        }

        response = client.post(
            '/api/v1/rate',
            json={'url': 'https://github.com/user/repo'}
        )
        assert response.status_code == 200
        mock_score.assert_called_once_with('https://github.com/user/repo')

    def test_url_too_long_rejected(self, client):
        """POST /rate with excessively long URL should be rejected."""
        url = "https://huggingface.co/" + "a" * 3000
        response = client.post(
            '/api/v1/rate',
            json={'url': url}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'too long' in data['message']
