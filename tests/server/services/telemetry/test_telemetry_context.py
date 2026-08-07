"""Unit tests for TelemetryRequestContext extraction from a Flask request."""

from flask import Flask, g, request

from src.server.services.telemetry.context import MAX_HEADER_LENGTH, TelemetryRequestContext
from src.server.services.telemetry.enums import TelemetryHeader


def _app():
    return Flask(__name__)


def _extract(headers=None):
    with _app().test_request_context(headers=headers or {}):
        return TelemetryRequestContext.extract(request)


def test_extracts_headers_and_sub():
    headers = {
        TelemetryHeader.SESSION_ID.value: "sess-1",
        TelemetryHeader.PROJECT_ID.value: "proj-X",
    }
    with _app().test_request_context(headers=headers):
        g.user_sub = "auth0|abc"
        ctx = TelemetryRequestContext.extract(request)
    assert ctx.user_sub == "auth0|abc"
    assert ctx.session_id == "sess-1"
    assert ctx.project_id == "proj-X"


def test_missing_values_are_none():
    ctx = _extract()
    assert ctx.user_sub is None
    assert ctx.session_id is None
    assert ctx.project_id is None


def test_extracts_client_identity_headers():
    ctx = _extract({
        TelemetryHeader.CLIENT_NAME.value: "revit",
        TelemetryHeader.CLIENT_VERSION.value: "0.3.0",
        TelemetryHeader.HOST_VERSION.value: "2024.2",
    })
    assert ctx.client_name == "revit"
    assert ctx.client_version == "0.3.0"
    assert ctx.host_version == "2024.2"


def test_client_identity_missing_is_none():
    ctx = _extract()
    assert ctx.client_name is None
    assert ctx.client_version is None
    assert ctx.host_version is None


def test_blank_header_is_none():
    """A whitespace-only header must not reach the payload as an empty string."""
    ctx = _extract({
        TelemetryHeader.CLIENT_NAME.value: "   ",
        TelemetryHeader.CLIENT_VERSION.value: "",
    })
    assert ctx.client_name is None
    assert ctx.client_version is None


def test_header_value_is_truncated():
    """Headers are unauthenticated input — oversized values are capped, not stored whole."""
    ctx = _extract({TelemetryHeader.CLIENT_VERSION.value: "v" * (MAX_HEADER_LENGTH + 50)})
    assert ctx.client_version == "v" * MAX_HEADER_LENGTH


def test_surrounding_whitespace_is_stripped():
    ctx = _extract({TelemetryHeader.CLIENT_NAME.value: "  web  "})
    assert ctx.client_name == "web"
