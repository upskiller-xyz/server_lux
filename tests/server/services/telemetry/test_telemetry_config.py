"""Unit tests for TelemetryConfig."""

import pytest

from src.server.services.telemetry.config import TelemetryConfig
from src.server.services.telemetry.enums import IdentityMode


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for key in ("TELEMETRY_SERVICE_URL", "TELEMETRY_ENABLED", "TELEMETRY_TIMEOUT_SECONDS", "TELEMETRY_IDENTITY_MODE"):
        monkeypatch.delenv(key, raising=False)


def test_disabled_without_url():
    assert TelemetryConfig().enabled is False


def test_enabled_when_url_set(monkeypatch):
    monkeypatch.setenv("TELEMETRY_SERVICE_URL", "http://telemetry:8086")
    config = TelemetryConfig()
    assert config.enabled is True
    assert config.events_url == "http://telemetry:8086/events"


def test_explicit_disable_overrides_url(monkeypatch):
    monkeypatch.setenv("TELEMETRY_SERVICE_URL", "http://telemetry:8086")
    monkeypatch.setenv("TELEMETRY_ENABLED", "false")
    assert TelemetryConfig().enabled is False


def test_trailing_slash_stripped(monkeypatch):
    monkeypatch.setenv("TELEMETRY_SERVICE_URL", "http://telemetry:8086/")
    assert TelemetryConfig().events_url == "http://telemetry:8086/events"


def test_identity_mode_defaults_to_none():
    assert TelemetryConfig().identity_mode is None


def test_identity_mode_parsed(monkeypatch):
    monkeypatch.setenv("TELEMETRY_IDENTITY_MODE", "identified")
    assert TelemetryConfig().identity_mode is IdentityMode.IDENTIFIED


def test_unknown_identity_mode_is_none(monkeypatch):
    monkeypatch.setenv("TELEMETRY_IDENTITY_MODE", "bogus")
    assert TelemetryConfig().identity_mode is None
