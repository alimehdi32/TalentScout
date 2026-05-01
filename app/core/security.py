"""
Security utilities — auth scaffold.

Currently a placeholder that always passes.
Set ENABLE_AUTH=true and implement JWT/API-key verification here
when you are ready to add authentication.
"""

from fastapi import HTTPException, Request, status
from app.core.config import settings


def verify_api_key(request: Request) -> None:
    """
    Placeholder API-key verification hook.

    When ENABLE_AUTH is True, validate the `X-API-Key` header.
    Raises HTTP 401 if key is missing or invalid.
    """
    if not settings.ENABLE_AUTH:
        return  # Auth disabled — allow all traffic

    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key != settings.SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )


# ── Future expansion hooks ────────────────────────────────────────────────────

def create_access_token(data: dict) -> str:
    """Scaffold: generate a JWT token (not yet implemented)."""
    raise NotImplementedError("JWT support not yet enabled.")


def decode_access_token(token: str) -> dict:
    """Scaffold: decode and validate a JWT token (not yet implemented)."""
    raise NotImplementedError("JWT support not yet enabled.")
