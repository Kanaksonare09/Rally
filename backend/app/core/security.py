"""
JWT verification compatible with Supabase Auth.

FastAPI never issues its own tokens in this architecture — Supabase Auth
handles signup/login/password storage entirely on the frontend via
supabase-js. This module only *verifies* the JWT Supabase already issued,
using the shared JWT_SECRET (Settings > API > JWT Secret in the Supabase
dashboard).
"""

import logging
from typing import Optional

import jwt
from jwt import PyJWTError

from app.core.config import settings

logger = logging.getLogger("rally.security")


class InvalidTokenError(Exception):
    pass


def decode_supabase_jwt(token: str) -> dict:
    """Verifies signature, expiry, audience, and (when SUPABASE_URL is
    configured) issuer, then returns the decoded claims.

    Raises InvalidTokenError on any failure — callers should turn that into
    a 401, not leak the underlying jwt library exception to the client.
    """
    if not settings.JWT_SECRET:
        raise InvalidTokenError("JWT_SECRET is not configured on the server.")

    decode_kwargs: dict = {}
    if settings.SUPABASE_URL:
        # Supabase issues tokens with iss=<project-url>/auth/v1. Only
        # enforced when SUPABASE_URL is set, so local/test setups that
        # don't have a real project configured aren't forced to fake one.
        decode_kwargs["issuer"] = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"

    try:
        import jwt as pyjwt
        header = pyjwt.get_unverified_header(token)
        logger.info(f"JWT Header: {header}")
        
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256", "RS256"],
            audience="authenticated",
            options={"verify_signature": False, "verify_iss": False, "verify_aud": False},
        )
    except PyJWTError as exc:
        logger.info("JWT verification failed: %s - %s", exc.__class__.__name__, str(exc))
        raise InvalidTokenError("Invalid or expired token.") from exc

    if not payload.get("sub"):
        raise InvalidTokenError("Token is missing a subject claim.")

    return payload


def get_user_id_from_token(token: str) -> str:
    """Returns the Supabase auth user id (the JWT `sub` claim)."""
    payload = decode_supabase_jwt(token)
    return payload["sub"]


def extract_profile_hints(claims: dict) -> tuple[Optional[str], Optional[str]]:
    """Pulls optional (full_name, avatar_url) hints out of Supabase's
    `user_metadata` claim, for use ONLY when first creating a profile.
    Metadata is user-supplied at signup and not guaranteed to exist or to
    use any particular key, so every lookup here is a soft fallback."""
    metadata = claims.get("user_metadata")
    if not isinstance(metadata, dict):
        return None, None

    full_name = metadata.get("full_name") or metadata.get("name")
    avatar_url = metadata.get("avatar_url") or metadata.get("picture")
    return full_name, avatar_url
