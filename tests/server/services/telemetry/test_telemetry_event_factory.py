"""Unit tests for TelemetryEventFactory."""

from datetime import datetime

from src.server.services.telemetry.enums import IdentityMode, TelemetryField
from src.server.services.telemetry.event_factory import TelemetryEventFactory


def _create(**overrides):
    base = dict(endpoint="run", duration_ms=123, success=True)
    base.update(overrides)
    return TelemetryEventFactory.create(**base)


def test_required_fields_present():
    event = _create()
    assert event[TelemetryField.ENDPOINT.value] == "run"
    assert event[TelemetryField.DURATION_MS.value] == 123
    assert event[TelemetryField.SUCCESS.value] is True
    assert len(event[TelemetryField.REQUEST_ID.value]) == 32  # uuid4 hex


def test_timestamp_is_iso8601():
    ts = _create()[TelemetryField.TIMESTAMP.value]
    # Raises if not parseable
    datetime.fromisoformat(ts)


def test_request_ids_are_unique():
    assert _create()[TelemetryField.REQUEST_ID.value] != _create()[TelemetryField.REQUEST_ID.value]


def test_optional_fields_omitted_when_absent():
    event = _create()
    for field in (TelemetryField.ERROR_CODE, TelemetryField.USER_SUB,
                  TelemetryField.PROJECT_ID, TelemetryField.IDENTITY_MODE,
                  TelemetryField.CLIENT_NAME, TelemetryField.CLIENT_VERSION,
                  TelemetryField.HOST_VERSION):
        assert field.value not in event


def test_error_code_included_when_set():
    event = _create(success=False, error_code="ServiceTimeoutError")
    assert event[TelemetryField.ERROR_CODE.value] == "ServiceTimeoutError"


def test_identity_and_identifiers_included():
    event = _create(user_sub="auth0|abc", project_id="proj-X", identity_mode=IdentityMode.IDENTIFIED)
    assert event[TelemetryField.USER_SUB.value] == "auth0|abc"
    assert event[TelemetryField.PROJECT_ID.value] == "proj-X"
    assert event[TelemetryField.IDENTITY_MODE.value] == "identified"


def test_client_identity_included():
    event = _create(client_name="revit", client_version="0.3.0", host_version="2024.2")
    assert event[TelemetryField.CLIENT_NAME.value] == "revit"
    assert event[TelemetryField.CLIENT_VERSION.value] == "0.3.0"
    assert event[TelemetryField.HOST_VERSION.value] == "2024.2"


def test_client_identity_fields_are_independent():
    """A client that sends only its name must not produce empty version fields."""
    event = _create(client_name="web")
    assert event[TelemetryField.CLIENT_NAME.value] == "web"
    assert TelemetryField.CLIENT_VERSION.value not in event
    assert TelemetryField.HOST_VERSION.value not in event
