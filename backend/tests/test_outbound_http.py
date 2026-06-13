from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services import outbound_http


@dataclass
class FakeResponse:
    status_code: int
    headers: dict[str, str]
    chunks: list[bytes]

    def iter_content(self, chunk_size: int = 32 * 1024):
        yield from self.chunks


class FakeSession:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = responses
        self.requests: list[tuple[str, str]] = []

    def mount(self, *_args, **_kwargs):
        return None

    def request(self, *, method: str, url: str, **_kwargs):
        self.requests.append((method, url))
        if not self.responses:
            raise AssertionError("unexpected request")
        return self.responses.pop(0)

    def close(self):
        return None


def test_validate_url_accepts_stable_https_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(outbound_http, "_resolve_host", lambda hostname: {"8.8.8.8"})

    scheme, host, port = outbound_http._validate_url(
        "https://8.8.8.8/path",
        require_https=True,
        allow_private_ips=True,
        allowed_ports={443},
        allowed_hosts=None,
        sensitive_hosts=None,
    )

    assert scheme == "https"
    assert host == "8.8.8.8"
    assert port == 443


def test_request_outbound_follows_redirect_and_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(
        [
            FakeResponse(302, {"location": "https://example.com/final"}, []),
            FakeResponse(200, {"content-type": "text/plain"}, [b"ok"]),
        ]
    )
    monkeypatch.setattr(outbound_http.requests, "Session", lambda: session)
    monkeypatch.setattr(outbound_http, "_resolve_host", lambda hostname: {"93.184.216.34"})

    response = outbound_http.request_outbound(
        url="https://example.com/start",
        allowed_hosts={"example.com"},
        allow_private_ips=False,
        max_redirects=2,
    )

    assert response.status_code == 200
    assert response.url == "https://example.com/final"
    assert response.text == "ok"
    assert session.requests[0][1] == "https://example.com/start"
    assert session.requests[1][1] == "https://example.com/final"


def test_request_outbound_rejects_large_response(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession([FakeResponse(200, {"content-type": "text/plain"}, [b"abc", b"def"])])
    monkeypatch.setattr(outbound_http.requests, "Session", lambda: session)
    monkeypatch.setattr(outbound_http, "_resolve_host", lambda hostname: {"93.184.216.34"})

    with pytest.raises(outbound_http.OutboundRequestError, match="Response too large"):
        outbound_http.request_outbound(
            url="https://example.com/file",
            allowed_hosts={"example.com"},
            allow_private_ips=False,
            max_bytes=2,
        )
