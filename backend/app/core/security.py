"""
JWT verification compatible with Supabase Auth.

FastAPI never issues its own tokens in this architecture — Supabase Auth
handles signup/login/password storage entirely on the frontend via
supabase-js. This module only *verifies* the JWT Supabase already issued.

Two verification paths, selected by the token's own (untrusted, but
allow-listed) `alg` header — never by anything the caller asserts:

- HS256, the shared-secret path — `JWT_SECRET` (Settings > API > JWT
  Secret in the Supabase dashboard). This is what every project created
  before Supabase's JWT Signing Keys rollout uses, and what the test
  suite's locally-signed tokens always use (see tests/conftest.py).
- ES256/RS256, the asymmetric path — newer Supabase projects (JWT
  Signing Keys enabled) sign tokens with a private key and publish the
  matching PUBLIC key at `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`.
  There is no shared secret to configure for these at all; verification
  fetches that public key (cached) instead.

Gating which key material is used strictly by an allow-listed `alg`
(never blindly trusting the header) avoids the classic algorithm-
confusion attack — an HS256 token can never be checked against the
JWKS-published public key, and an ES256/RS256 token can never be checked
against JWT_SECRET.
"""

import logging
from typing import Optional

import jwt
from jwt import PyJWKClient, PyJWTError

from app.core.config import settings

logger = logging.getLogger("rally.security")

_ASYMMETRIC_ALGORITHMS = {"ES256", "RS256"}


class InvalidTokenError(Exception):
    pass


_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> Optional[PyJWKClient]:
    """Lazily built and cached for the life of the process — constructing
    a PyJWKClient doesn't itself hit the network; it fetches (and caches
    for its `lifespan`) the JWKS on first actual use. None when
    SUPABASE_URL isn't configured, since there's nowhere to fetch it from."""
    global _jwks_client
    if not settings.SUPABASE_URL:
        return None
    if _jwks_client is None:
        jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True, timeout=5)
    return _jwks_client


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
        alg = jwt.get_unverified_header(token).get("alg")
    except PyJWTError as exc:
        logger.info("JWT header parsing failed: %s", exc.__class__.__name__)
        raise InvalidTokenError("Invalid or expired token.") from exc

    try:
        if alg == settings.JWT_ALGORITHM:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                audience="authenticated",
                **decode_kwargs,
            )
        elif alg in _ASYMMETRIC_ALGORITHMS:
            jwks_client = _get_jwks_client()
            if jwks_client is None:
                raise InvalidTokenError(
                    "Received an asymmetrically-signed token but SUPABASE_URL is not configured to fetch its signing key."
                )
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
                **decode_kwargs,
            )
        else:
            raise InvalidTokenError(f"Unsupported token signing algorithm: {alg!r}.")
    except InvalidTokenError:
        raise
    except PyJWTError as exc:
        logger.info("JWT verification failed: %s", exc.__class__.__name__)
        raise InvalidTokenError("Invalid or expired token.") from exc
    except Exception as exc:
        # A JWKS fetch/parse failure (network error, unknown kid, bad
        # response) surfaces from PyJWKClient as assorted non-PyJWTError
        # exceptions — a token this server can't verify is still just a
        # 401, never a raw 500.
        logger.info("JWT verification failed while resolving its signing key: %s", exc.__class__.__name__)
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
