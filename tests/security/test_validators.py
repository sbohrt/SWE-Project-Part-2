# tests/security/test_validators.py
"""
Tests for input validation.

SECURITY TEST: Verify URL validation prevents SSRF attacks.
"""
import pytest

from swe_project.api.validators import validate_model_url, _is_private_address


class TestURLValidation:
    """Test URL validation to prevent SSRF attacks."""

    def test_valid_huggingface_url(self):
        """Valid Hugging Face URL should pass validation."""
        url = "https://huggingface.co/bert-base-uncased"
        is_valid, error = validate_model_url(url)
        assert is_valid
        assert error == ""

    def test_valid_github_url(self):
        """Valid GitHub URL should pass validation."""
        url = "https://github.com/user/repo"
        is_valid, error = validate_model_url(url)
        assert is_valid
        assert error == ""

    def test_empty_url_rejected(self):
        """Empty URL should be rejected."""
        is_valid, error = validate_model_url("")
        assert not is_valid
        assert "non-empty string" in error

    def test_none_url_rejected(self):
        """None URL should be rejected."""
        is_valid, error = validate_model_url(None)
        assert not is_valid
        assert "non-empty string" in error

    def test_url_too_long_rejected(self):
        """URL longer than 2048 chars should be rejected."""
        url = "https://huggingface.co/" + "a" * 2050
        is_valid, error = validate_model_url(url)
        assert not is_valid
        assert "too long" in error

    def test_non_http_scheme_rejected(self):
        """Non-HTTP/HTTPS schemes should be rejected."""
        urls = [
            "ftp://huggingface.co/model",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>"
        ]
        for url in urls:
            is_valid, error = validate_model_url(url)
            assert not is_valid, f"URL {url} should be rejected"
            assert "HTTP or HTTPS" in error

    def test_localhost_rejected(self):
        """Localhost URLs should be rejected."""
        urls = [
            "http://localhost/api",
            "http://127.0.0.1/api",
            "http://0.0.0.0/api"
        ]
        for url in urls:
            is_valid, error = validate_model_url(url)
            assert not is_valid, f"URL {url} should be rejected"
            assert "Private addresses" in error

    def test_private_ip_ranges_rejected(self):
        """Private IP addresses should be rejected."""
        urls = [
            "http://10.0.0.1/api",           # 10.0.0.0/8
            "http://172.16.0.1/api",         # 172.16.0.0/12
            "http://172.31.255.255/api",     # 172.16.0.0/12
            "http://192.168.1.1/api",        # 192.168.0.0/16
            "http://169.254.169.254/api"     # AWS metadata endpoint
        ]
        for url in urls:
            is_valid, error = validate_model_url(url)
            assert not is_valid, f"Private IP {url} should be rejected"
            assert "Private addresses" in error

    def test_non_whitelisted_domain_rejected(self):
        """Non-whitelisted domains should be rejected."""
        urls = [
            "https://evil.com/model",
            "https://attacker.net/payload",
            "https://example.com/test"
        ]
        for url in urls:
            is_valid, error = validate_model_url(url)
            assert not is_valid, f"URL {url} should be rejected"
            assert "Domain not allowed" in error
            assert "huggingface.co" in error  # Error message should list allowed domains

    def test_url_without_domain_rejected(self):
        """URL without domain should be rejected."""
        url = "https:///path"
        is_valid, error = validate_model_url(url)
        assert not is_valid
        assert "valid domain" in error


class TestPrivateAddressDetection:
    """Test private address detection helper."""

    def test_localhost_variants(self):
        """All localhost variants should be detected."""
        assert _is_private_address("localhost")
        assert _is_private_address("127.0.0.1")
        assert _is_private_address("::1")
        assert _is_private_address("0.0.0.0")

    def test_private_ip_ranges(self):
        """All private IP ranges should be detected."""
        assert _is_private_address("10.0.0.1")
        assert _is_private_address("10.255.255.255")
        assert _is_private_address("172.16.0.1")
        assert _is_private_address("172.31.255.255")
        assert _is_private_address("192.168.0.1")
        assert _is_private_address("192.168.255.255")

    def test_link_local_addresses(self):
        """Link-local addresses should be detected."""
        assert _is_private_address("169.254.1.1")
        assert _is_private_address("169.254.169.254")  # AWS metadata

    def test_public_ips_not_flagged(self):
        """Public IP addresses should not be flagged as private."""
        # These are not private (though we still block them via domain whitelist)
        assert not _is_private_address("8.8.8.8")
        assert not _is_private_address("1.1.1.1")

    def test_invalid_ips_flagged(self):
        """Invalid IP addresses should be flagged as private (fail-secure)."""
        assert _is_private_address("256.256.256.256")
        assert _is_private_address("999.999.999.999")

    def test_public_domains_not_flagged(self):
        """Public domains should not be flagged as private."""
        assert not _is_private_address("huggingface.co")
        assert not _is_private_address("github.com")
        assert not _is_private_address("example.com")
