"""Login. See app/auth.py for the scheme and its limits."""

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import create_token, verify_password
from ..config import Settings, get_settings
from ..schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, settings: Settings = Depends(get_settings)):
    if not settings.admin_password or not settings.secret_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Admin access is not configured on this server.",
        )

    if not verify_password(body.password, settings):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect password.")

    token, ttl = create_token(settings)
    return TokenResponse(token=token, expires_in=ttl)
