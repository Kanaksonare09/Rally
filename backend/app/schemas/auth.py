from typing import Optional

from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    """Returned by get_current_user(). Carries a couple of extra optional
    hints (sourced from Supabase user_metadata, for first-time profile
    creation only) beyond the minimal {id, email} shape — those hints are
    never included in an API response, only `id` and `email` are."""

    id: str
    email: Optional[str] = None
    full_name_hint: Optional[str] = None
    avatar_url_hint: Optional[str] = None


class ProfileOut(BaseModel):
    model_config = {"from_attributes": True}

    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class MeResponse(BaseModel):
    id: str
    email: Optional[str] = None
    profile: Optional[ProfileOut] = None
