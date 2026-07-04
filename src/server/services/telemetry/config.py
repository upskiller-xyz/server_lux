import os
from typing import Optional

from .enums import IdentityMode


class TelemetryConfig:
    """Deployment configuration for telemetry emission, read from the environment.

    Single responsibility: expose telemetry settings; no I/O, no payload logic.
    Telemetry is opt-in and disabled unless TELEMETRY_SERVICE_URL is set.
    """

    def __init__(self) -> None:
        self._url = os.getenv("TELEMETRY_SERVICE_URL", "").rstrip("/")
        enabled_flag = os.getenv("TELEMETRY_ENABLED", "true").lower() == "true"
        self._enabled = enabled_flag and bool(self._url)
        self._timeout = float(os.getenv("TELEMETRY_TIMEOUT_SECONDS", "2"))

        mode_raw = os.getenv("TELEMETRY_IDENTITY_MODE")
        self._identity_mode = IdentityMode.by_value(mode_raw) if mode_raw else None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def events_url(self) -> str:
        return f"{self._url}/events"

    @property
    def timeout(self) -> float:
        return self._timeout

    @property
    def identity_mode(self) -> Optional[IdentityMode]:
        """Identity mode to request, or None to defer to the telemetry server default."""
        return self._identity_mode
