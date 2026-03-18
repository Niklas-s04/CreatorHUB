from __future__ import annotations

import pytest

from app.services.outbound_http import OutboundRequestError, _validate_url


def test_ssrf_rejects_localhost() -> None:
    with pytest.raises(OutboundRequestError, match="localhost blocked"):
        _validate_url(
            "https://localhost/api",
            require_https=True,
            allow_private_ips=False,
            allowed_ports={443},
            allowed_hosts=None,
            sensitive_hosts=None,
        )


def test_ssrf_rejects_private_ip() -> None:
    with pytest.raises(OutboundRequestError, match="blocked IP"):
        _validate_url(
            "https://10.0.0.5/resource",
            require_https=True,
            allow_private_ips=False,
            allowed_ports={443},
            allowed_hosts=None,
            sensitive_hosts=None,
        )


def test_ssrf_rejects_non_https_when_required() -> None:
    with pytest.raises(OutboundRequestError, match="Only HTTPS"):
        _validate_url(
            "http://8.8.8.8/resource",
            require_https=True,
            allow_private_ips=True,
            allowed_ports={80, 443},
            allowed_hosts=None,
            sensitive_hosts=None,
        )


def test_ssrf_enforces_host_allowlist() -> None:
    with pytest.raises(OutboundRequestError, match="allowlist"):
        _validate_url(
            "https://example.com/file",
            require_https=True,
            allow_private_ips=True,
            allowed_ports={443},
            allowed_hosts={"api.example.com"},
            sensitive_hosts=None,
        )


def test_ssrf_requires_explicit_allowlist_for_sensitive_host() -> None:
    with pytest.raises(OutboundRequestError, match="Sensitive"):
        _validate_url(
            "https://sensitive.example.com/data",
            require_https=True,
            allow_private_ips=True,
            allowed_ports={443},
            allowed_hosts=set(),
            sensitive_hosts={"sensitive.example.com"},
        )


def test_ssrf_accepts_valid_public_target() -> None:
    scheme, host, port = _validate_url(
        "https://8.8.8.8/resolve",
        require_https=True,
        allow_private_ips=True,
        allowed_ports={443},
        allowed_hosts=None,
        sensitive_hosts=None,
    )

    assert scheme == "https"
    assert host == "8.8.8.8"
    assert port == 443
