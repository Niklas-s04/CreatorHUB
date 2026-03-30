from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Callable

from fastapi import Request
from redis import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.logging_config import log_security_event
from app.core.security import decode_token, validate_csrf_token


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        hsts_seconds: int = 31536000,
        trust_proxy_headers: bool = False,
        env: str = "prod",
    ) -> None:
        super().__init__(app)
        self.hsts_seconds = hsts_seconds
        self.trust_proxy_headers = trust_proxy_headers
        self.env = env.lower()

    def _is_https(self, request: Request) -> bool:
        if request.url.scheme == "https":
            return True
        if self.trust_proxy_headers:
            proto = request.headers.get("x-forwarded-proto", "")
            if proto.split(",")[0].strip().lower() == "https":
                return True
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=(), browsing-topics=()"
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'; form-action 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; upgrade-insecure-requests",
        )

        if self.env == "prod" and self._is_https(request) and self.hsts_seconds > 0:
            response.headers.setdefault(
                "Strict-Transport-Security", f"max-age={self.hsts_seconds}; includeSubDomains"
            )

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, max_body_size: int = 2_000_000) -> None:
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_body_size:
                    log_security_event(
                        "request_rejected_body_too_large",
                        request=request,
                        details={
                            "content_length": content_length,
                            "max_body_size": self.max_body_size,
                        },
                    )
                    return JSONResponse(
                        status_code=413, content={"detail": "Request body too large"}
                    )
            except ValueError:
                log_security_event(
                    "request_rejected_invalid_content_length",
                    request=request,
                    details={"content_length": content_length},
                )
                return JSONResponse(
                    status_code=400, content={"detail": "Invalid Content-Length header"}
                )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        redis_url: str,
        redis_prefix: str = "rl",
        trust_proxy_headers: bool = False,
        global_limit: int = 240,
        window_seconds: int = 60,
        auth_limit: int = 10,
    ) -> None:
        super().__init__(app)
        self.redis_prefix = redis_prefix
        self.trust_proxy_headers = trust_proxy_headers
        self.global_limit = global_limit
        self.window_seconds = window_seconds
        self.auth_limit = auth_limit

        self._redis: Redis | None = None
        self._redis_script = None
        try:
            self._redis = Redis.from_url(
                redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
            )
            self._redis.ping()
            self._redis_script = self._redis.register_script(
                """
                local key = KEYS[1]
                local now = tonumber(ARGV[1])
                local window_ms = tonumber(ARGV[2])
                local limit = tonumber(ARGV[3])
                local member = ARGV[4]

                redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window_ms)
                redis.call('ZADD', key, now, member)

                local count = redis.call('ZCARD', key)
                redis.call('PEXPIRE', key, window_ms + 2000)

                if count > limit then
                    return 1
                end
                return 0
                """
            )
        except Exception:
            self._redis = None
            self._redis_script = None

        self._requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _get_client_ip(self, request: Request) -> str:
        xff = request.headers.get("x-forwarded-for")
        if self.trust_proxy_headers and xff:
            return xff.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    def _limit_for_path(self, path: str) -> int:
        if path.startswith("/api/auth/token"):
            return self.auth_limit
        if path.startswith("/api/auth/register-request"):
            return max(2, self.auth_limit // 2)
        if path.startswith("/api/auth/setup-admin-password"):
            return max(2, self.auth_limit // 2)
        return self.global_limit

    def _is_limited(self, key: tuple[str, str], now: float, limit: int) -> bool:
        with self._lock:
            q = self._requests[key]
            cutoff = now - self.window_seconds
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit:
                return True
            q.append(now)
            return False

    def _is_limited_redis(self, ip: str, path: str, limit: int) -> bool | None:
        if not self._redis or not self._redis_script:
            return None

        now_ms = int(time.time() * 1000)
        window_ms = int(self.window_seconds * 1000)
        key = f"{self.redis_prefix}:{path}:{ip}"
        member = f"{now_ms}-{secrets.token_hex(4)}"
        try:
            result = self._redis_script(keys=[key], args=[now_ms, window_ms, limit, member])
            return bool(int(result))
        except RedisError:
            return None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if path.startswith("/health"):
            return await call_next(request)

        ip = self._get_client_ip(request)
        limit = self._limit_for_path(path)
        now = time.monotonic()

        redis_limited = self._is_limited_redis(ip, path, limit)
        if redis_limited is True:
            log_security_event(
                "request_rate_limited",
                request=request,
                details={"path": path, "ip": ip, "limit": limit, "mode": "redis"},
            )
            return JSONResponse(status_code=429, content={"detail": "Too many requests"})
        if redis_limited is None and self._is_limited((ip, path), now, limit):
            log_security_event(
                "request_rate_limited",
                request=request,
                details={"path": path, "ip": ip, "limit": limit, "mode": "in_memory"},
            )
            return JSONResponse(status_code=429, content={"detail": "Too many requests"})

        return await call_next(request)


class CsrfProtectionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, auth_cookie_name: str, csrf_cookie_name: str) -> None:
        super().__init__(app)
        self.auth_cookie_name = auth_cookie_name
        self.csrf_cookie_name = csrf_cookie_name
        self.unsafe_methods = {"POST", "PUT", "PATCH", "DELETE"}
        self.exempt_paths = {"/api/auth/token"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method not in self.unsafe_methods:
            return await call_next(request)

        path = request.url.path
        if not path.startswith("/api"):
            return await call_next(request)

        if path in self.exempt_paths:
            return await call_next(request)

        auth_cookie = request.cookies.get(self.auth_cookie_name)
        if not auth_cookie:
            return await call_next(request)

        csrf_cookie = request.cookies.get(self.csrf_cookie_name)
        csrf_header = request.headers.get("x-csrf-token")
        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            log_security_event("csrf_validation_failed", request=request)
            return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})

        try:
            payload = decode_token(auth_cookie)
            sid = payload.get("sid")
            token_type = payload.get("typ")
            if token_type != "access" or not sid:
                raise ValueError("invalid session context")
            if not validate_csrf_token(csrf_cookie, str(sid)):
                raise ValueError("invalid csrf token")
        except Exception:
            log_security_event("csrf_validation_failed", request=request)
            return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})

        return await call_next(request)
