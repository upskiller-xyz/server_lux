"""Unit tests for caller-identity telemetry (X-Client-Name/-Version, X-Host-Version)."""

from flask import Flask, g, jsonify

from src.server.enums import HTTPHeader
from src.server.telemetry import (
    CLIENT_NAME_KEY,
    CLIENT_VERSION_KEY,
    HOST_VERSION_KEY,
    UNKNOWN_CLIENT_VALUE,
    ClientTelemetryResolver,
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
