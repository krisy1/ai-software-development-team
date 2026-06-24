from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import decode_access_token, verify_api_key
from app.db.session import get_db_session

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


async def verify_jwt_token(authorization: str | None = Header(None)) -> str | None:
    """Extract and validate a JWT from the Authorization header.

    Expects ``Authorization: Bearer <token>``.
    Returns the subject (user ID) on success, or ``None`` if auth is disabled.
    """
    if authorization is None:
        if not settings.SECRET_KEY:
            return None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format (expected 'Bearer <token>')",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
        return str(payload.get("sub", ""))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def verify_api_key_header(x_api_key: str | None = Header(None)) -> None:
    """Dependency to verify API key for authenticated endpoints."""
    if x_api_key is None:
        if not settings.API_KEY:
            return None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    if not verify_api_key(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


async def verify_auth(
    x_api_key: str | None = Header(None),
    authorization: str | None = Header(None),
) -> str | None:
    """Combined auth: tries API key first, then JWT Bearer token.

    Returns the authenticated subject (user ID) if available,
    or ``None`` if no credentials are configured (development mode).
    """
    if not settings.API_KEY and not settings.SECRET_KEY:
        return None

    if x_api_key is not None:
        if not verify_api_key(x_api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        return "api-key-user"

    if authorization is not None:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header format",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            payload = decode_access_token(token)
            return str(payload.get("sub", ""))
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )
