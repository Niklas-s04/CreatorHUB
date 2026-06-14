from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.outbound_http import OutboundResponse, request_outbound


def fetch_external(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    max_bytes: int | None = None,
    timeout_connect: int | None = None,
    timeout_read: int | None = None,
    allowed_hosts: set[str] | None = None,
    allow_private_ips: bool = False,
    db: Session | None = None,
    params: dict[str, Any] | None = None,
) -> OutboundResponse:
    return request_outbound(
        url=url,
        method="GET",
        headers=headers,
        params=params,
        timeout_connect=timeout_connect,
        timeout_read=timeout_read,
        max_bytes=max_bytes,
        allowed_hosts=allowed_hosts,
        allow_private_ips=allow_private_ips,
        require_https=True,
        db=db,
    )
