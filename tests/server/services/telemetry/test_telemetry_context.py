"""Unit tests for TelemetryRequestContext extraction from a Flask request."""

from flask import Flask, g, request

from src.server.services.telemetry.context import TelemetryRequestContext
from src.server.services.telemetry.enums import TelemetryHeader


def _app():
    return Flask(__name__)


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
    with _app().test_request_context():
        ctx = TelemetryRequestContext.extract(request)
    assert ctx.user_sub is None
    assert ctx.session_id is None
    assert ctx.project_id is None
