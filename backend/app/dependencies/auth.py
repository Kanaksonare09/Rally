"""
Auth dependency chain:

    Authorization header -> HTTPBearer -> decode_supabase_jwt()
        -> get_current_user() -> get_current_profile()

FastAPI caches Depends() results per request, so using get_current_user
both directly in an endpoint and transitively via get_current_profile does
NOT re-verify the JWT twice.
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import InvalidTokenError, decode_supabase_jwt, extract_profile_hints
from app.models.profile import Profile
from app.schemas.auth import AuthenticatedUser
from app.services.profile_service import get_or_create_profile

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    try:
        claims = decode_supabase_jwt(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    full_name_hint, avatar_url_hint = extract_profile_hints(claims)

    # The id always comes from the verified token's `sub` claim — nothing
    # from the request body, query string, or headers can override it.
    return AuthenticatedUser(
        id=claims["sub"],
        email=claims.get("email"),
        full_name_hint=full_name_hint,
        avatar_url_hint=avatar_url_hint,
    )


def get_current_user_id(user: AuthenticatedUser = Depends(get_current_user)) -> str:
    """Thin wrapper for endpoints that only need the id, not the full user."""
    return user.id


def get_current_profile(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Profile:
    return get_or_create_profile(
        db,
        user_id=user.id,
        full_name_hint=user.full_name_hint,
        avatar_url_hint=user.avatar_url_hint,
    )
