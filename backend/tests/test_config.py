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
