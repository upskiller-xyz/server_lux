"""Unit tests for TelemetryReporter (coordinator)."""

from unittest.mock import Mock

from src.server.services.telemetry.enums import IdentityMode, TelemetryField
from src.server.services.telemetry.event_factory import TelemetryEventFactory
from src.server.services.telemetry.reporter import TelemetryReporter


def _reporter(enabled=True, identity_mode=None, emitter=None):
    config = Mock()
    config.enabled = enabled
    config.identity_mode = identity_mode
    return TelemetryReporter(config, TelemetryEventFactory(), emitter or Mock())


def test_disabled_does_not_emit():
    emitter = Mock()
    _reporter(enabled=False, emitter=emitter).report("run", 10, True)
    emitter.emit.assert_not_called()


def test_enabled_emits_built_payload():
    emitter = Mock()
    _reporter(emitter=emitter).report("run", 10, True, user_sub="auth0|x", session_id="s1")
    emitter.emit.assert_called_once()
    payload, kwargs = emitter.emit.call_args.args[0], emitter.emit.call_args.kwargs
    assert payload[TelemetryField.ENDPOINT.value] == "run"
    assert payload[TelemetryField.USER_SUB.value] == "auth0|x"
    assert kwargs["session_id"] == "s1"


def test_identity_mode_from_config_applied():
    emitter = Mock()
    _reporter(identity_mode=IdentityMode.IDENTIFIED, emitter=emitter).report("run", 10, True)
    payload = emitter.emit.call_args.args[0]
    assert payload[TelemetryField.IDENTITY_MODE.value] == "identified"
