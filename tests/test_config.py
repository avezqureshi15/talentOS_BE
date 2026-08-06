import pytest

from app.core.config import Settings

_DEV_REMINDER = 0.002778
_DEV_ESCALATION = 0.005556


def _settings(**overrides) -> Settings:
    return Settings(DATABASE_URL="postgresql://test:test@localhost/test", _env_file=None, **overrides)


def test_uat_uses_dev_timings():
    s = _settings(APP_ENV="uat")
    assert s.FORM_REMINDER_HOURS == pytest.approx(_DEV_REMINDER)
    assert s.FORM_ESCALATION_HOURS == pytest.approx(_DEV_ESCALATION)
    assert s.FORM_EXPIRY_HOURS == 24
    assert s.AI_ROUND_EVALUATION_DELAY_MINUTES == 1


def test_staging_uses_dev_timings():
    s = _settings(APP_ENV="staging")
    assert s.FORM_REMINDER_HOURS == pytest.approx(_DEV_REMINDER)
    assert s.AI_ROUND_EVALUATION_DELAY_MINUTES == 1


def test_production_uses_prod_timings():
    s = _settings(APP_ENV="production")
    assert s.FORM_REMINDER_HOURS == 2
    assert s.FORM_ESCALATION_HOURS == 3
    assert s.FORM_EXPIRY_HOURS == 24
    assert s.AI_ROUND_EVALUATION_DELAY_MINUTES == 0


def test_explicit_override_wins_over_app_env_default():
    s = _settings(APP_ENV="uat", FORM_REMINDER_HOURS=5, FORM_EXPIRY_HOURS=48)
    assert s.FORM_REMINDER_HOURS == 5
    assert s.FORM_EXPIRY_HOURS == 48
    assert s.FORM_ESCALATION_HOURS == pytest.approx(_DEV_ESCALATION)
    assert s.AI_ROUND_EVALUATION_DELAY_MINUTES == 1


def test_explicit_override_wins_in_production():
    s = _settings(APP_ENV="production", FORM_REMINDER_HOURS=1)
    assert s.FORM_REMINDER_HOURS == 1
    assert s.FORM_ESCALATION_HOURS == 3
