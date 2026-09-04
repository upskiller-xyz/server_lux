import logging
from dataclasses import dataclass
from typing import Optional

from flask import Flask, Response, g, request

from .enums import HTTPHeader

logger = logging.getLogger("logger")

# Sent by an older client build that predates these headers — telemetry must
# never fail a request over a missing header, so this is the fallback value.
UNKNOWN_CLIENT_VALUE = "unknown"

# flask.g attribute keys the resolver writes to and downstream code reads from.
CLIENT_NAME_KEY = "client_name"
CLIENT_VERSION_KEY = "client_version"
HOST_VERSION_KEY = "host_version"


@dataclass(frozen=True)
class ClientTelemetry:
    """The caller-identity headers resolved for one request.

    ``client_name``/``client_version`` identify the calling plugin (e.g.
    "revit", "v0.3.0"); ``host_version`` is the version of the application the
    plugin is embedded in (e.g. Revit itself, "2024.1.1").
    """

    client_name: str
    client_version: str
    host_version: str

    @property
    def as_dict(self) -> dict:
        return {
            CLIENT_NAME_KEY: self.client_name,
            CLIENT_VERSION_KEY: self.client_version,
            HOST_VERSION_KEY: self.host_version,
        }


class ClientTelemetryResolver:
    """Reads the caller-identity headers off the current request.

    Every header is optional (an older plugin build may not send them yet), so
    a missing header resolves to ``UNKNOWN_CLIENT_VALUE`` rather than failing
    the request.
    """

    def resolve(self) -> ClientTelemetry:
        return ClientTelemetry(
            client_name=self._header(HTTPHeader.CLIENT_NAME),
            client_version=self._header(HTTPHeader.CLIENT_VERSION),
            host_version=self._header(HTTPHeader.HOST_VERSION),
        )

    def _header(self, header: HTTPHeader) -> str:
        return request.headers.get(header.value) or UNKNOWN_CLIENT_VALUE


class RequestTelemetryLogger:
    """Logs one structured line per request, tagging it with the caller
    identity so log aggregation can group by client and plugin version."""

    LOG_TEMPLATE = (
        "caller request: client_name={client_name} client_version={client_version} "
        "host_version={host_version} path={path} status={status}"
    )

    def __init__(self, resolver: Optional[ClientTelemetryResolver] = None):
        self._resolver = resolver or ClientTelemetryResolver()

    def record_request(self) -> None:
        telemetry = self._resolver.resolve()
        setattr(g, CLIENT_NAME_KEY, telemetry.client_name)
        setattr(g, CLIENT_VERSION_KEY, telemetry.client_version)
        setattr(g, HOST_VERSION_KEY, telemetry.host_version)

    def record_response(self, response: Response) -> Response:
        logger.info(
            self.LOG_TEMPLATE.format(
                client_name=getattr(g, CLIENT_NAME_KEY, UNKNOWN_CLIENT_VALUE),
                client_version=getattr(g, CLIENT_VERSION_KEY, UNKNOWN_CLIENT_VALUE),
                host_version=getattr(g, HOST_VERSION_KEY, UNKNOWN_CLIENT_VALUE),
                path=request.path,
                status=response.status_code,
            )
        )
        return response


class TelemetryMiddleware:
    """Wires the caller-identity resolver into a Flask app's request cycle:
    every request gets a grouped-by-caller line in the logs, and ``flask.g``
    carries the resolved identity for any downstream consumer."""

    def __init__(self, telemetry_logger: Optional[RequestTelemetryLogger] = None):
        self._logger = telemetry_logger or RequestTelemetryLogger()

    def register(self, app: Flask) -> None:
        app.before_request(self._logger.record_request)
        app.after_request(self._logger.record_response)
