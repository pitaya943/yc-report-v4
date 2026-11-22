import pytest

from app.core.config import ConfigError, load_settings
from tests.support.cli import run_app

URL = "postgresql://app:hunter2@db.example/yc"


def problems(environ: dict[str, str]) -> list[str]:
    with pytest.raises(ConfigError) as caught:
        load_settings(environ)
    return caught.value.problems


def test_defaults_when_only_the_database_is_given():
    settings = load_settings({"DATABASE_URL": URL})

    assert settings.database_url == URL
    assert settings.app_env == "development"
    assert settings.password_hash_profile == "standard"
    assert settings.trusted_proxy_hops == 0
    assert settings.clock_offset_minutes == 0


def test_missing_database_url_is_refused_by_name():
    found = problems({})
    assert len(found) == 1 and found[0].startswith("DATABASE_URL")


def test_every_problem_is_listed_at_once():
    found = problems({"APP_ENV": "staging", "TRUSTED_PROXY_HOPS": "-1", "CLOCK_OFFSET_MINUTES": "soon"})

    assert len(found) == 4
    for name in ("DATABASE_URL", "APP_ENV", "TRUSTED_PROXY_HOPS", "CLOCK_OFFSET_MINUTES"):
        assert any(problem.startswith(name) for problem in found), name


def test_an_unknown_hash_profile_is_refused():
    found = problems({"DATABASE_URL": URL, "PASSWORD_HASH_PROFILE": "quick"})
    assert len(found) == 1 and found[0].startswith("PASSWORD_HASH_PROFILE")


def test_production_refuses_the_fast_hash_profile():
    found = problems({"DATABASE_URL": URL, "APP_ENV": "production", "PASSWORD_HASH_PROFILE": "fast"})
    assert len(found) == 1 and found[0].startswith("PASSWORD_HASH_PROFILE")


def test_production_refuses_a_clock_offset():
    found = problems({"DATABASE_URL": URL, "APP_ENV": "production", "CLOCK_OFFSET_MINUTES": "30"})
    assert len(found) == 1 and found[0].startswith("CLOCK_OFFSET_MINUTES")


@pytest.mark.parametrize("env", ["development", "test"])
def test_outside_production_fast_hashing_and_a_clock_offset_are_accepted(env):
    settings = load_settings(
        {"DATABASE_URL": URL, "APP_ENV": env, "PASSWORD_HASH_PROFILE": "fast", "CLOCK_OFFSET_MINUTES": "30"}
    )
    assert settings.password_hash_profile == "fast"
    assert settings.clock_offset_minutes == 30


def test_production_with_standard_settings_is_accepted():
    assert load_settings({"DATABASE_URL": URL, "APP_ENV": "production"}).app_env == "production"


def test_absent_storage_and_bank_key_are_not_configured_rather_than_errors():
    settings = load_settings({"DATABASE_URL": URL})
    assert settings.storage_configured is False
    assert settings.bank_key_configured is False


def test_present_storage_and_bank_key_are_configured():
    settings = load_settings({"DATABASE_URL": URL, "STORAGE_BACKEND": "s3", "BANK_KEY": "k"})
    assert settings.storage_configured is True
    assert settings.bank_key_configured is True


def test_check_config_stops_and_names_every_problem():
    done = run_app("check-config", APP_ENV="production", PASSWORD_HASH_PROFILE="fast", CLOCK_OFFSET_MINUTES="5")

    assert done.returncode != 0
    for name in ("DATABASE_URL", "PASSWORD_HASH_PROFILE", "CLOCK_OFFSET_MINUTES"):
        assert name in done.stderr


def test_serve_stops_when_database_url_is_missing():
    done = run_app("serve")

    assert done.returncode != 0
    assert "DATABASE_URL" in done.stderr


def test_check_config_reports_each_setting_without_printing_the_database_url():
    done = run_app("check-config", DATABASE_URL=URL)

    assert done.returncode == 0
    lines = done.stdout.splitlines()
    assert "STORAGE_BACKEND：未設定" in lines
    assert "BANK_KEY：未設定" in lines
    assert "APP_ENV：development" in lines
    assert "hunter2" not in done.stdout + done.stderr


def test_check_config_reports_storage_and_bank_key_as_configured_without_their_values():
    done = run_app("check-config", DATABASE_URL=URL, STORAGE_BACKEND="s3", BANK_KEY="very-secret")

    assert done.returncode == 0
    lines = done.stdout.splitlines()
    assert "STORAGE_BACKEND：已設定" in lines
    assert "BANK_KEY：已設定" in lines
    assert "very-secret" not in done.stdout + done.stderr
