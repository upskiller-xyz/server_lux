import logging
import threading
from typing import Any, Dict, Optional

import requests

from .config import TelemetryConfig
from .enums import TelemetryHeader, TelemetryLogKey

logger = logging.getLogger("logger")


class TelemetryEmitter:
    """Fire-and-forget transport to the telemetry server.

    Single responsibility: send one event without ever affecting the caller.
    Posts on a background thread with a short timeout and swallows every error —
    telemetry must never block or break the user-facing request.
    """

    def __init__(self, config: TelemetryConfig) -> None:
        self._config = config

    def emit(self, payload: Dict[str, Any], session_id: Optional[str] = None) -> None:
        if not self._config.enabled:
            logger.debug("%s endpoint=%s", TelemetryLogKey.DISABLED.value, payload.get("endpoint"))
            return
        thread = threading.Thread(
            target=self._post,
            args=(payload, session_id),
            daemon=True,
        )
        thread.start()

    def _post(self, payload: Dict[str, Any], session_id: Optional[str]) -> None:
        headers = {TelemetryHeader.SESSION_ID.value: session_id} if session_id else None
        try:
            requests.post(
                self._config.events_url,
                json=payload,
                headers=headers,
                timeout=self._config.timeout,
            )
            logger.debug("%s endpoint=%s", TelemetryLogKey.EMITTED.value, payload.get("endpoint"))
        except Exception as e:
            # Best-effort: never propagate. Log at WARNING so telemetry outages are visible.
            logger.warning("%s endpoint=%s error=%s", TelemetryLogKey.FAILED.value, payload.get("endpoint"), e)
