import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_load_without_env_file():
    """Settings must construct even with no .env present — every secret
    field is Optional so a missing .env fails at point-of-use, not at
    import time."""
    s = Settings(_env_file=None)
    assert s.PROJECT_NAME == "RALLY API"
    assert s.API_V1_STR == "/api/v1"


def test_cors_origins_parses_single_origin():
    s = Settings(_env_file=None, FRONTEND_URL="http://localhost:3000")
    assert s.cors_origins == ["http://localhost:3000"]


def test_cors_origins_parses_multiple_origins():
    s = Settings(_env_file=None, FRONTEND_URL="http://localhost:3000, https://rally.app")
    assert s.cors_origins == ["http://localhost:3000", "https://rally.app"]


def test_no_hardcoded_secret_defaults():
    """Regression guard: secrets must never ship with a real-looking default."""
    s = Settings(_env_file=None)
    assert s.JWT_SECRET is None
    assert s.SUPABASE_SERVICE_ROLE_KEY is None
    assert s.DATABASE_URL is None


def test_cors_allowed_origins_takes_priority_over_frontend_url():
    s = Settings(_env_file=None, FRONTEND_URL="http://old.example.com", CORS_ALLOWED_ORIGINS="http://new.example.com")
    assert s.cors_origins == ["http://new.example.com"]


def test_frontend_url_still_works_when_cors_allowed_origins_unset():
    s = Settings(_env_file=None, FRONTEND_URL="http://localhost:3000")
    assert s.cors_origins == ["http://localhost:3000"]


# ---- production fail-fast config validation --------------------------------


def test_development_never_requires_production_secrets():
    Settings(_env_file=None)  # must not raise


def test_test_environment_never_requires_production_secrets():
    Settings(_env_file=None, ENVIRONMENT="test")  # must not raise


def test_unrecognized_environment_value_is_treated_like_development():
    Settings(_env_file=None, ENVIRONMENT="staging")  # must not raise


def test_production_without_required_secrets_fails_fast():
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, ENVIRONMENT="production")
    assert "DATABASE_URL" in str(exc_info.value)


def test_production_missing_only_one_secret_still_fails():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None, ENVIRONMENT="production",
            DATABASE_URL="postgresql://x", REDIS_URL="redis://x", SUPABASE_URL="https://x",
            SUPABASE_ANON_KEY="x", SUPABASE_SERVICE_ROLE_KEY="x",
            # JWT_SECRET deliberately omitted
        )
    assert "JWT_SECRET" in str(exc_info.value)


def test_production_with_every_required_secret_starts_cleanly():
    s = Settings(
        _env_file=None, ENVIRONMENT="production",
        DATABASE_URL="postgresql://x", REDIS_URL="redis://x", SUPABASE_URL="https://x",
        SUPABASE_ANON_KEY="x", SUPABASE_SERVICE_ROLE_KEY="x", JWT_SECRET="x",
    )
    assert s.ENVIRONMENT == "production"
