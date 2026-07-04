from enum import Enum

from src.utils.extended_enum import ExtendedEnumMixin


class TelemetryField(ExtendedEnumMixin, Enum):
    """Payload field names sent to the telemetry server (no magic strings)."""

    REQUEST_ID = "request_id"
    ENDPOINT = "endpoint"
    TIMESTAMP = "timestamp"
    DURATION_MS = "duration_ms"
    SUCCESS = "success"
    ERROR_CODE = "error_code"
    USER_SUB = "user_sub"
    IDENTITY_MODE = "identity_mode"
    PROJECT_ID = "project_id"


class IdentityMode(ExtendedEnumMixin, Enum):
    """Identity handling requested of the telemetry server (mirrors server_telemetry)."""

    IDENTIFIED = "identified"
    ANONYMOUS = "anonymous"


class TelemetryHeader(ExtendedEnumMixin, Enum):
    """Inbound headers forwarded to the telemetry server for request grouping."""

    SESSION_ID = "X-Session-Id"
    PROJECT_ID = "X-Project-Id"


class TelemetryLogKey(ExtendedEnumMixin, Enum):
    """Structured log keys for telemetry emission (greppable, stable)."""

    EMITTED = "telemetry.emitted"
    DISABLED = "telemetry.disabled"
    FAILED = "telemetry.failed"
