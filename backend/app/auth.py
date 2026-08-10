"""Admin authentication.

STUB BY DESIGN — this is a single shared password, not user accounts. It fits a
chapter site with one or two officers who edit the calendar, and it is the piece
to replace first if that assumption stops holding.

What it does: POST the password to /api/auth/login, get back an HMAC-signed
token of the form "<expiry>.<signature>". The signature covers the expiry, so a
token can't be extended without the secret. Nothing is stored server-side, which
means tokens survive a restart and cannot be revoked individually before expiry
— if you need revocation, add a token table.

Rate limiting of login attempts lives in routers/auth.py (in-process): Caddy,
unlike nginx, ships no limit_req equivalent, so the proxy can't do it for us.
"""

import hmac
import secrets
import time
from hashlib import sha256

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), sha256).hexdigest()


def create_token(settings: Settings) -> tuple[str, int]:
    """Return (token, seconds_until_expiry)."""
    ttl = settings.token_ttl_hours * 3600
    expires_at = int(time.time()) + ttl
    payload = str(expires_at)
    return f"{payload}.{_sign(payload, settings.secret_key)}", ttl


def verify_password(candidate: str, settings: Settings) -> bool:
    # compare_digest keeps the check constant-time, so a wrong password doesn't
    # leak how many leading characters were right.
    return secrets.compare_digest(candidate, settings.admin_password)


def _token_is_valid(token: str, settings: Settings) -> bool:
    payload, _, signature = token.partition(".")
    if not payload or not signature:
        return False
    if not secrets.compare_digest(signature, _sign(payload, settings.secret_key)):
        return False
    try:
        return int(payload) > int(time.time())
    except ValueError:
        return False


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    """Dependency for every write endpoint. Raises 401 unless the token checks out."""
    # Fail closed: an unconfigured server must not accept writes, or a fresh
    # deploy that forgot the .env would let anyone edit the calendar.
    if not settings.admin_password or not settings.secret_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Admin access is not configured on this server.",
        )

    if credentials is None or not _token_is_valid(credentials.credentials, settings):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
