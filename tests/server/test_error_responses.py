"""Client-safe error mapping (no internal details leak to the caller)."""

import pytest
from flask import Flask

from src.server.enums import ErrorType, HTTPStatus
from src.server.exceptions import (
    MergeValidationError,
    RequestValidationError,
    ServiceAuthorizationError,
    ServiceConnectionError,
    ServiceResponseError,
    ServiceTimeoutError,
)
from src.server.response_builder import ErrorResponseBuilder


@pytest.fixture
def app():
    app = Flask(__name__)
    with app.app_context():
        yield app


def _build(exception: Exception):
    response, status = ErrorResponseBuilder().build_from_exception(exception)
    return response.get_json(), status


def test_unexpected_exception_is_generic_500(app):
    body, status = _build(KeyError("/srv/app/secret_path.py"))
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR.value
    assert "secret_path" not in body["error"]
    assert body["error_type"] == ErrorType.INTERNAL_ERROR.value


def test_internal_value_error_is_not_echoed(app):
    body, status = _build(ValueError("Encoder service did not return image data. Available keys: ['x']"))
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR.value
    assert "Available keys" not in body["error"]


def test_internal_service_exception_is_not_echoed(app):
    body, status = _build(MergeValidationError("window 'w1' mask must be 2D"))
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR.value
    assert "w1" not in body["error"]


def test_request_validation_error_is_400_with_message(app):
    body, status = _build(RequestValidationError("No windows provided"))
    assert status == HTTPStatus.BAD_REQUEST.value
    assert body["error"] == "No windows provided"
    assert body["error_type"] == ErrorType.VALIDATION_ERROR.value


def test_upstream_validation_error_passes_through(app):
    body, status = _build(ServiceResponseError("encoder", "/encode", 400, "Invalid window height"))
    assert status == 400
    assert body["error"] == "Invalid window height"


@pytest.mark.parametrize("upstream_status", [401, 500, 503])
def test_upstream_other_errors_are_summarised_as_bad_gateway(app, upstream_status):
    body, status = _build(ServiceResponseError("model", "/run", upstream_status, "Traceback: /app/x.py"))
    assert status == HTTPStatus.BAD_GATEWAY.value
    assert "Traceback" not in body["error"]


def test_upstream_authorization_error_is_not_403(app):
    """A refused service credential must not tell the caller to log in again."""
    body, status = _build(ServiceAuthorizationError("obstruction", "/obstruction", "bad X-Auth-Token"))
    assert status == HTTPStatus.BAD_GATEWAY.value
    assert "X-Auth-Token" not in body["error"]


def test_upstream_connection_and_timeout(app):
    _, status = _build(ServiceConnectionError("stats", "/", "http://stats-service:8085"))
    assert status == HTTPStatus.SERVICE_UNAVAILABLE.value
    body, status = _build(ServiceTimeoutError("model", "/run", 300))
    assert status == HTTPStatus.GATEWAY_TIMEOUT.value
    assert body["error"] == "model service timeout"
