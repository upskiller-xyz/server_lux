import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .enums import IdentityMode, TelemetryField


class TelemetryEventFactory:
    """Builds telemetry event payloads (Factory Pattern).

    Single responsibility: turn a request outcome into a server_telemetry payload.
    Generates the request_id and timestamp; omits optional fields when absent so the
    telemetry server applies its own defaults (e.g. identity mode).
    """

    @classmethod
    def create(
        cls,
        endpoint: str,
        duration_ms: int,
        success: bool,
        error_code: Optional[str] = None,
        user_sub: Optional[str] = None,
        project_id: Optional[str] = None,
        identity_mode: Optional[IdentityMode] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            TelemetryField.REQUEST_ID.value: uuid.uuid4().hex,
            TelemetryField.ENDPOINT.value: endpoint,
            TelemetryField.TIMESTAMP.value: cls._now(),
            TelemetryField.DURATION_MS.value: duration_ms,
            TelemetryField.SUCCESS.value: success,
        }
        if error_code is not None:
            payload[TelemetryField.ERROR_CODE.value] = error_code
        if user_sub:
            payload[TelemetryField.USER_SUB.value] = user_sub
        if project_id:
            payload[TelemetryField.PROJECT_ID.value] = project_id
        if identity_mode is not None:
            payload[TelemetryField.IDENTITY_MODE.value] = identity_mode.value
        return payload

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
