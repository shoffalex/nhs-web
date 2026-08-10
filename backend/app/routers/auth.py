"""Login. See app/auth.py for the scheme and its limits.

Brute-force throttling lives here, in-process: Caddy (unlike nginx) ships no
request rate limiting, so the API can't delegate it to the proxy. Only failed
attempts count against the limit, and the state is a dict in memory — a
restart forgets it, which is fine for the attack this guards against
(scripted guessing of one shared password).
"""

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..auth import create_token, verify_password
from ..config import Settings, get_settings
from ..schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

_WINDOW_SECONDS = 60
_MAX_FAILURES = 10

# ip -> monotonic timestamps of recent failed attempts
_failures: dict[str, list[float]] = {}


def _check_throttle(ip: str) -> None:
    now = time.monotonic()
    recent = [t for t in _failures.get(ip, []) if now - t < _WINDOW_SECONDS]
    if recent:
        _failures[ip] = recent
    else:
        _failures.pop(ip, None)

    if len(recent) >= _MAX_FAILURES:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed logins. Try again in a minute.",
        )


def _record_failure(ip: str) -> None:
    _failures.setdefault(ip, []).append(time.monotonic())
    # One shared password means a tiny working set; the cap only guards the
    # dict against a flood of spoofed source addresses.
    if len(_failures) > 10_000:
        _failures.clear()


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
):
    # request.client reflects X-Forwarded-For: uvicorn runs with
    # --proxy-headers and trusts only the loopback proxy (Caddy).
    ip = request.client.host if request.client else "unknown"
    _check_throttle(ip)

    if not settings.admin_password or not settings.secret_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Admin access is not configured on this server.",
        )

    if not verify_password(body.password, settings):
        _record_failure(ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect password.")

    token, ttl = create_token(settings)
    return TokenResponse(token=token, expires_in=ttl)
