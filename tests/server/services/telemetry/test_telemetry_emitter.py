"""Unit tests for TelemetryEmitter (fire-and-forget transport)."""

from unittest.mock import Mock, patch

from src.server.services.telemetry.emitter import TelemetryEmitter
from src.server.services.telemetry.enums import TelemetryHeader


def _config(enabled=True, url="http://telemetry:8086/events", timeout=2.0):
    config = Mock()
    config.enabled = enabled
    config.events_url = url
    config.timeout = timeout
    return config


def test_disabled_does_not_post():
    emitter = TelemetryEmitter(_config(enabled=False))
    with patch("src.server.services.telemetry.emitter.requests.post") as post:
        emitter.emit({"endpoint": "run"})
        post.assert_not_called()


def test_post_sends_payload_and_session_header():
    emitter = TelemetryEmitter(_config())
    with patch("src.server.services.telemetry.emitter.requests.post") as post:
        emitter._post({"endpoint": "run"}, session_id="sess-1")
        post.assert_called_once()
        _, kwargs = post.call_args
        assert kwargs["json"] == {"endpoint": "run"}
        assert kwargs["headers"] == {TelemetryHeader.SESSION_ID.value: "sess-1"}
        assert kwargs["timeout"] == 2.0


def test_post_without_session_sends_no_headers():
    emitter = TelemetryEmitter(_config())
    with patch("src.server.services.telemetry.emitter.requests.post") as post:
        emitter._post({"endpoint": "run"}, session_id=None)
        assert post.call_args.kwargs["headers"] is None


def test_post_swallows_errors():
    emitter = TelemetryEmitter(_config())
    with patch("src.server.services.telemetry.emitter.requests.post", side_effect=RuntimeError("boom")):
        # Must not raise — telemetry is best-effort.
        emitter._post({"endpoint": "run"}, session_id=None)
