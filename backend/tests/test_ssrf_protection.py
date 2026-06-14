from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services import outbound_http
from app.services.outbound import fetch_external
from app.services.outbound_http import OutboundRequestError, _validate_url


@dataclass
class FakeResponse:
    status_code: int
    headers: dict[str, str]
    chunks: list[bytes]

    def iter_content(self, chunk_size: int = 32 * 1024):
        yield from self.chunks


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response

    def mount(self, *_args, **_kwargs):
        return None

    def request(self, **_kwargs):
        return self.response

    def close(self):
        return None


def test_ssrf_localhost_blocked() -> None:
    with pytest.raises(OutboundRequestError, match="localhost blocked"):
        _validate_url(
            "https://localhost/admin",
            require_https=True,
            allow_private_ips=False,
            allowed_ports={443},
            allowed_hosts=None,
            sensitive_hosts=None,
        )


def test_ssrf_private_ip_blocked() -> None:
    with pytest.raises(OutboundRequestError, match="blocked IP"):
        _validate_url(
            "https://192.168.1.10/metadata",
            require_https=True,
            allow_private_ips=False,
            allowed_ports={443},
            allowed_hosts=None,
            sensitive_hosts=None,
        )


def test_ssrf_oversized_response_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(outbound_http, "_resolve_host", lambda hostname: {"93.184.216.34"})
    monkeypatch.setattr(
        outbound_http.requests,
        "Session",
        lambda: FakeSession(FakeResponse(200, {"content-type": "text/plain"}, [b"abc", b"def"])),
    )

    with pytest.raises(OutboundRequestError, match="Response too large"):
        fetch_external(
            "https://example.com/file.txt",
            allowed_hosts={"example.com"},
            max_bytes=4,
        )
