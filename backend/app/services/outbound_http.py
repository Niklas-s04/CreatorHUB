from __future__ import annotations

import ipaddress
import socket
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from sqlalchemy.orm import Session
from urllib3.util.retry import Retry

from app.core.config import settings
from app.models.audit import AuditLog


class OutboundRequestError(RuntimeError):
    pass


@dataclass
class OutboundResponse:
    status_code: int
    url: str
    content: bytes
    headers: dict[str, str]
    elapsed_ms: int

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        import json

        return json.loads(self.text)


def _allowed_ports() -> set[int]:
    raw = [p.strip() for p in (settings.OUTBOUND_ALLOWED_PORTS or "443").split(",") if p.strip()]
    out: set[int] = set()
    for part in raw:
        try:
            port = int(part)
            if 1 <= port <= 65535:
                out.add(port)
        except Exception:
            continue
    return out or {443}


def _allowlist_hosts() -> set[str]:
    return {
        h.strip().lower() for h in (settings.OUTBOUND_ALLOWLIST_HOSTS or "").split(",") if h.strip()
    }


def _sensitive_allowlist_hosts() -> set[str]:
    return {
        h.strip().lower()
        for h in (settings.OUTBOUND_SENSITIVE_ALLOWLIST_HOSTS or "").split(",")
        if h.strip()
    }


def _is_blocked_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    if ip.is_loopback:
        return True
    if ip.is_link_local:
        return True
    if ip.is_private:
        return True
    if ip.is_reserved or ip.is_multicast or ip.is_unspecified:
        return True
    return False


def _resolve_host(hostname: str) -> set[str]:
    records = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    ips: set[str] = set()
    for r in records:
        sockaddr = r[4]
        if sockaddr and sockaddr[0]:
            ips.add(sockaddr[0])
    return ips


def _validate_url(
    url: str,
    *,
    require_https: bool,
    allow_private_ips: bool,
    allowed_ports: set[int],
    allowed_hosts: set[str] | None,
    sensitive_hosts: set[str] | None,
) -> tuple[str, str, int]:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower().strip(".")

    if not host:
        raise OutboundRequestError("Missing host")
    if host == "localhost":
        raise OutboundRequestError("localhost blocked")

    if require_https and scheme != "https":
        raise OutboundRequestError("Only HTTPS is allowed")
    if scheme not in {"https", "http"}:
        raise OutboundRequestError("Unsupported URL scheme")

    port = parsed.port
    if port is None:
        port = 443 if scheme == "https" else 80
    if port not in allowed_ports:
        raise OutboundRequestError(f"Port {port} is not allowed")

    if allowed_hosts and host not in allowed_hosts:
        raise OutboundRequestError("Target host not in allowlist")

    if (
        sensitive_hosts
        and host in sensitive_hosts
        and (not allowed_hosts or host not in allowed_hosts)
    ):
        raise OutboundRequestError("Sensitive target requires explicit allowlist")

    try:
        ip = ipaddress.ip_address(host)
        ips = {str(ip)}
    except ValueError:
        ips1 = _resolve_host(host)
        time.sleep(0.02)
        ips2 = _resolve_host(host)
        ips = ips1 & ips2
        if not ips:
            raise OutboundRequestError("DNS resolution unstable or empty")

    if not allow_private_ips and settings.OUTBOUND_BLOCK_PRIVATE_RANGES:
        for ip in ips:
            if _is_blocked_ip(ip):
                raise OutboundRequestError("Target resolves to blocked IP range")

    return scheme, host, port


def _log_outbound(
    db: Session | None,
    *,
    url: str,
    method: str,
    status: str,
    status_code: int | None,
    duration_ms: int,
    error: str | None,
) -> None:
    if db is None:
        return
    db.add(
        AuditLog(
            actor_id=None,
            actor_name="system",
            action="outbound.request",
            entity_type="network",
            entity_id=None,
            description=f"{method.upper()} {url}",
            meta={
                "status": status,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "error": error,
            },
        )
    )


def request_outbound(
    *,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    data: Any = None,
    timeout_connect: int | None = None,
    timeout_read: int | None = None,
    max_bytes: int | None = None,
    max_redirects: int | None = None,
    retries: int | None = None,
    require_https: bool | None = None,
    allow_private_ips: bool = False,
    allowed_hosts: set[str] | None = None,
    db: Session | None = None,
) -> OutboundResponse:
    request_headers = {"User-Agent": "creatorhub-outbound/1.0", **(headers or {})}
    timeout = (
        timeout_connect
        if timeout_connect is not None
        else settings.OUTBOUND_CONNECT_TIMEOUT_SECONDS,
        timeout_read if timeout_read is not None else settings.OUTBOUND_READ_TIMEOUT_SECONDS,
    )
    byte_limit = max_bytes if max_bytes is not None else settings.OUTBOUND_MAX_RESPONSE_BYTES
    redirect_limit = max_redirects if max_redirects is not None else settings.OUTBOUND_MAX_REDIRECTS
    retry_count = retries if retries is not None else settings.OUTBOUND_RETRIES
    enforce_https = settings.OUTBOUND_REQUIRE_HTTPS if require_https is None else require_https

    ports = _allowed_ports()
    sensitive_hosts = _sensitive_allowlist_hosts()

    session = requests.Session()
    retry_cfg = Retry(
        total=max(0, retry_count),
        connect=max(0, retry_count),
        read=max(0, retry_count),
        status=max(0, retry_count),
        allowed_methods=frozenset(["GET", "HEAD"]),
        status_forcelist=[429, 500, 502, 503, 504],
        backoff_factor=0.3,
        raise_on_status=False,
        redirect=0,
    )
    adapter = HTTPAdapter(max_retries=retry_cfg)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    current_url = url
    start = time.perf_counter()
    resp: requests.Response | None = None
    try:
        for _ in range(redirect_limit + 1):
            _validate_url(
                current_url,
                require_https=enforce_https,
                allow_private_ips=allow_private_ips,
                allowed_ports=ports,
                allowed_hosts=allowed_hosts,
                sensitive_hosts=sensitive_hosts,
            )
            resp = session.request(
                method=method.upper(),
                url=current_url,
                headers=request_headers,
                params=params,
                json=json_body,
                data=data,
                timeout=timeout,
                allow_redirects=False,
                stream=True,
            )
            if 300 <= resp.status_code < 400 and resp.headers.get("location"):
                current_url = urljoin(current_url, resp.headers["location"])
                continue
            break
        else:
            raise OutboundRequestError("Too many redirects")

        chunks: list[bytes] = []
        received = 0
        for chunk in resp.iter_content(chunk_size=32 * 1024):
            if not chunk:
                continue
            received += len(chunk)
            if received > byte_limit:
                raise OutboundRequestError("Response too large")
            chunks.append(chunk)

        content = b"".join(chunks)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        if resp.status_code >= 400:
            _log_outbound(
                db,
                url=current_url,
                method=method,
                status="error",
                status_code=resp.status_code,
                duration_ms=elapsed_ms,
                error=f"HTTP {resp.status_code}",
            )
            raise OutboundRequestError(f"HTTP {resp.status_code}")

        _log_outbound(
            db,
            url=current_url,
            method=method,
            status="ok",
            status_code=resp.status_code,
            duration_ms=elapsed_ms,
            error=None,
        )
        return OutboundResponse(
            status_code=resp.status_code,
            url=current_url,
            content=content,
            headers={k.lower(): v for k, v in resp.headers.items()},
            elapsed_ms=elapsed_ms,
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        status_code = resp.status_code if resp is not None else None
        _log_outbound(
            db,
            url=current_url,
            method=method,
            status="error",
            status_code=status_code,
            duration_ms=elapsed_ms,
            error=str(exc)[:500],
        )
        raise
    finally:
        session.close()
