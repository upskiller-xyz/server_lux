"""Unit tests for caller-identity telemetry (X-Client-Name/-Version, X-Host-Version)."""

from flask import Flask, g, jsonify

from src.server.enums import HTTPHeader
from src.server.telemetry import (
    CLIENT_NAME_KEY,
    CLIENT_VERSION_KEY,
    EMPTY_HEADER_VALUE,
    HOST_VERSION_KEY,
    MAX_HEADER_VALUE_LENGTH,
    UNKNOWN_CLIENT_VALUE,
    ClientTelemetryResolver,
    HeaderValueSanitizer,
    TelemetryMiddleware,
)


def _app_with_route() -> Flask:
    app = Flask(__name__)
    TelemetryMiddleware().register(app)

    @app.route("/ping")
    def ping():
        return jsonify(
            {
                CLIENT_NAME_KEY: getattr(g, CLIENT_NAME_KEY),
                CLIENT_VERSION_KEY: getattr(g, CLIENT_VERSION_KEY),
                HOST_VERSION_KEY: getattr(g, HOST_VERSION_KEY),
            }
        )

    return app


def test_resolver_reads_all_three_headers():
    resolver = ClientTelemetryResolver()
    app = Flask(__name__)
    headers = {
        HTTPHeader.CLIENT_NAME.value: "revit",
        HTTPHeader.CLIENT_VERSION.value: "v0.3.0",
        HTTPHeader.HOST_VERSION.value: "2024.1.1",
    }
    with app.test_request_context("/", headers=headers):
        telemetry = resolver.resolve()

    assert telemetry.client_name == "revit"
    assert telemetry.client_version == "v0.3.0"
    assert telemetry.host_version == "2024.1.1"


def test_resolver_falls_back_to_unknown_when_headers_missing():
    resolver = ClientTelemetryResolver()
    app = Flask(__name__)
    with app.test_request_context("/"):
        telemetry = resolver.resolve()

    assert telemetry.client_name == UNKNOWN_CLIENT_VALUE
    assert telemetry.client_version == UNKNOWN_CLIENT_VALUE
    assert telemetry.host_version == UNKNOWN_CLIENT_VALUE


def test_middleware_exposes_identity_on_g_for_the_route():
    client = _app_with_route().test_client()
    headers = {
        HTTPHeader.CLIENT_NAME.value: "web",
        HTTPHeader.CLIENT_VERSION.value: "v1.2.3",
        HTTPHeader.HOST_VERSION.value: "chrome-129",
    }
    response = client.get("/ping", headers=headers)
    body = response.get_json()

    assert body[CLIENT_NAME_KEY] == "web"
    assert body[CLIENT_VERSION_KEY] == "v1.2.3"
    assert body[HOST_VERSION_KEY] == "chrome-129"


def test_middleware_defaults_to_unknown_without_headers():
    client = _app_with_route().test_client()
    body = client.get("/ping").get_json()

    assert body[CLIENT_NAME_KEY] == UNKNOWN_CLIENT_VALUE
    assert body[CLIENT_VERSION_KEY] == UNKNOWN_CLIENT_VALUE
    assert body[HOST_VERSION_KEY] == UNKNOWN_CLIENT_VALUE


def test_sanitizer_strips_control_characters_that_could_forge_log_lines():
    # Arrange
    hostile = "revit\r\n2026-09-24 - logger - fake log line"

    # Act
    sanitized = HeaderValueSanitizer.sanitize(hostile)

    # Assert
    assert "\r" not in sanitized
    assert "\n" not in sanitized
    assert sanitized == "revit2026-09-24 - logger - fake log line"


def test_sanitizer_truncates_amplifying_values():
    # Arrange
    huge = "x" * (MAX_HEADER_VALUE_LENGTH * 10)

    # Act
    sanitized = HeaderValueSanitizer.sanitize(huge)

    # Assert
    assert len(sanitized) == MAX_HEADER_VALUE_LENGTH


def test_sanitizer_collapses_empty_or_control_only_values():
    # Arrange / Act / Assert
    assert HeaderValueSanitizer.sanitize("") == EMPTY_HEADER_VALUE
    assert HeaderValueSanitizer.sanitize("\x00\x1b\x7f") == EMPTY_HEADER_VALUE


def test_resolver_sanitizes_hostile_headers_end_to_end():
    # Arrange
    resolver = ClientTelemetryResolver()
    app = Flask(__name__)
    # Werkzeug refuses raw newlines in a test request context (as a real HTTP
    # server would reject them on the wire), so smuggle them the way a client
    # that does get them through would: as a single header value with CRLF
    # replaced by spaces — the sanitizer must still strip other control chars.
    headers = {HTTPHeader.CLIENT_NAME.value: "revit\x1b[31mFAKE 200 OK"}
    with app.test_request_context("/", headers=headers):
        # Act
        telemetry = resolver.resolve()

    # Assert — no escape sequence survives into the value that lands on `g`
    assert "\x1b" not in telemetry.client_name
    assert telemetry.client_name == "revit[31mFAKE 200 OK"
