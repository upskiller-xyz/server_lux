"""Per-call tracing records: one JSON line per outbound remote-service call.

Shaped after :class:`StageTimer` (same context-manager pattern, same
``[prefix]`` greppability) but emits structured JSON rather than prose, so a
reduce script can compute percentiles/error rates without parsing log text.

    with CallRecorder(EncoderService.name, "encode") as record:
        response = client.post(url, payload)

    # on exit, always (ok or error):
    # [call] {"rid": "...", "service": "encoder", "endpoint": "encode",
    #         "ms": 842, "outcome": "ok"}

The endpoint label is ``endpoint.value`` ("encode", not "/encode") — the same
form ``EndpointType`` carries, with no leading slash.

The correlation id (``rid``) comes from nginx's ``$request_id``, forwarded as
``X-Request-Id`` and read into a contextvar by :class:`RequestIdMiddleware`.
A contextvar (not ``flask.g``) is required because the per-window fan-out runs
the service calls in worker threads: ``contextvars`` are what
``asyncio.to_thread`` propagates into them.
"""
import contextvars
import json
import logging
import time
from types import TracebackType
from typing import Optional, Type

from flask import g, request

from ...enums import HTTPHeader, ServiceName
from ...telemetry import HeaderValueSanitizer

logger = logging.getLogger("logger")

# No nginx in front (local dev, tests): no X-Request-Id arrives, and the
# records must still be emitted rather than dropped — just uncorrelated.
UNKNOWN_REQUEST_ID = "-"


class CallOutcome:
    """Outcome values stamped on each [call] record."""

    OK = "ok"
    ERROR = "error"


class CallRecord:
    """Keys of the JSON record — one place so emit and reduce cannot drift."""

    TS = "ts"
    RID = "rid"
    SERVICE = "service"
    ENDPOINT = "endpoint"
    MS = "ms"
    OUTCOME = "outcome"
    WAIT_MS = "wait_ms"


class RequestIdContext:
    """Holds the current request's correlation id in a contextvar.

    ``to_thread`` copies the calling context into worker threads, so an id set
    on the request thread is visible inside every fan-out call — which is the
    entire point (one id per pipeline run, across all parallel window calls).
    """

    _id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default=UNKNOWN_REQUEST_ID)

    @classmethod
    def set(cls, value: str) -> contextvars.Token:
        return cls._id.set(value)

    @classmethod
    def reset(cls, token: contextvars.Token) -> None:
        cls._id.reset(token)

    @classmethod
    def get(cls) -> str:
        return cls._id.get()


class RequestIdMiddleware:
    """Reads nginx's ``X-Request-Id`` into the request context and echoes it
    on the response (so a client-side report and the backend records can be
    joined on the same id).

    The contextvar is reset after the response: gunicorn reuses worker threads
    across requests, and a leaked id would stamp the next header-less
    request's ``[call]`` records with the previous request's id.
    """

    _TOKEN_KEY = "request_id_token"

    def register(self, app) -> None:
        app.before_request(self._capture)
        app.after_request(self._echo)

    def _capture(self) -> None:
        # Attacker-influenceable header: control characters (log forging via
        # fake log lines) and unbounded length (log amplification — the rid is
        # copied into every [call] record and the per-window fan-out multiplies
        # that). The telemetry sanitizer bounds both and collapses a
        # control-only value to "-" — reuse it rather than a second policy.
        raw = request.headers.get(HTTPHeader.REQUEST_ID.value, "")
        # Always set (never inherit a previous request's id on this thread):
        # a missing or control-only header sanitizes to "-", the unknown id.
        setattr(g, self._TOKEN_KEY, RequestIdContext.set(HeaderValueSanitizer.sanitize(raw)))

    def _echo(self, response):
        # A before_request that short-circuits (auth guard, maintenance mode)
        # skips _capture, but after_request still runs — getattr default keeps
        # that from turning into an AttributeError/500 on every request.
        response.headers[HTTPHeader.REQUEST_ID.value] = RequestIdContext.get()
        token = getattr(g, self._TOKEN_KEY, None)
        if token is not None:
            RequestIdContext.reset(token)
        return response


class CallRecorder:
    """Logs one structured ``[call]`` line for one outbound service call.

    The service name is always the caller's ``ServiceName`` enum value (never
    parsed from the URL): ``HTTPClient._parse_service_name`` returns the first
    *path segment*, which mislabels every call ("encode" for the encoder, not
    "encoder").

    ``wait_ms`` records time spent acquiring a gate before the call (e.g. the
    obstruction concurrency semaphore). Unset for ungated calls — a reduce
    script treats a missing key as no wait, rather than 0, so "no gate" and
    "instant gate" stay distinguishable.
    """

    LOG_PREFIX = "[call]"

    def __init__(self, service: ServiceName, endpoint: str):
        self._service = service
        self._endpoint = endpoint
        self._t0 = 0.0
        self._wait_ms: float | None = None

    @property
    def service(self) -> ServiceName:
        return self._service

    @property
    def endpoint(self) -> str:
        return self._endpoint

    def record_wait(self, wait_ms: float) -> None:
        """Stamp a gate-acquisition time measured by the caller (the caller
        wraps the gate, not this recorder — it cannot see the wait itself)."""
        self._wait_ms = wait_ms

    def __enter__(self) -> "CallRecorder":
        self._t0 = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> bool:
        record = self.build_record(outcome=CallOutcome.ERROR if exc_type else CallOutcome.OK)
        logger.info(self.LOG_PREFIX + " %s", json.dumps(record))
        return False  # never suppress exceptions

    def build_record(self, outcome: str) -> dict:
        elapsed_ms = (time.perf_counter() - self._t0) * 1000
        record = {
            CallRecord.TS: time.time(),
            CallRecord.RID: RequestIdContext.get(),
            CallRecord.SERVICE: self._service.value,
            CallRecord.ENDPOINT: self._endpoint,
            CallRecord.MS: round(elapsed_ms, 1),
            CallRecord.OUTCOME: outcome,
        }
        if self._wait_ms is not None:
            record[CallRecord.WAIT_MS] = round(self._wait_ms, 1)
        return record