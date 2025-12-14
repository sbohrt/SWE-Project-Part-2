# src/swe_project/api/validators.py
"""
Input validation utilities for API endpoints.

SECURITY FIX: URL validation to prevent SSRF attacks.
"""
import re
from typing import Tuple
from urllib.parse import urlparse


# Allowed domains for model URLs
ALLOWED_DOMAINS = [
    "huggingface.co",
    "github.com",
    "www.huggingface.co",
    "www.github.com",
]


def validate_model_url(url: str) -> Tuple[bool, str]:
    """
    Validate a model URL to prevent SSRF attacks.

    Security checks:
    1. URL must be properly formatted
    2. Must use HTTP or HTTPS scheme only
    3. Domain must be in the whitelist
    4. No localhost, private IPs, or internal addresses

    Args:
        url: The URL to validate

    Returns:
        (is_valid, error_message)
        - If valid: (True, "")
        - If invalid: (False, "error message")
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string"

    # Check URL length (prevent DoS)
    if len(url) > 2048:
        return False, "URL too long (max 2048 characters)"

    # Parse the URL
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    # Check scheme
    if parsed.scheme not in ['http', 'https']:
        return False, "URL must use HTTP or HTTPS scheme"

    # Check if domain is provided
    if not parsed.netloc:
        return False, "URL must have a valid domain"

    # Extract hostname (without port)
    hostname = parsed.netloc.split(':')[0].lower()

    # Block localhost and private IPs
    if _is_private_address(hostname):
        return False, "Private addresses and localhost are not allowed"

    # Check against whitelist
    if hostname not in ALLOWED_DOMAINS:
        allowed = ", ".join(ALLOWED_DOMAINS)
        return False, f"Domain not allowed. Allowed domains: {allowed}"

    return True, ""


def _is_private_address(hostname: str) -> bool:
    """
    Check if hostname is localhost or a private IP address.

    Blocks:
    - localhost, 127.0.0.1, ::1
    - Private IPv4: 10.x.x.x, 172.16-31.x.x, 192.168.x.x
    - Link-local: 169.254.x.x
    - Metadata endpoints: 169.254.169.254 (AWS)
    """
    # Localhost variants
    if hostname in ['localhost', '127.0.0.1', '::1', '0.0.0.0']:
        return True

    # Check for private IPv4 ranges
    ipv4_pattern = re.compile(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$')
    match = ipv4_pattern.match(hostname)

    if match:
        octets = [int(x) for x in match.groups()]

        # Validate octets
        if any(octet > 255 for octet in octets):
            return True  # Invalid IP, block it

        # Private ranges
        if octets[0] == 10:  # 10.0.0.0/8
            return True
        if octets[0] == 172 and 16 <= octets[1] <= 31:  # 172.16.0.0/12
            return True
        if octets[0] == 192 and octets[1] == 168:  # 192.168.0.0/16
            return True
        if octets[0] == 169 and octets[1] == 254:  # 169.254.0.0/16 (link-local + metadata)
            return True
        if octets[0] == 127:  # 127.0.0.0/8 (loopback)
            return True

    return False
