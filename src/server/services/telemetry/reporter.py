import logging
from typing import Optional

from .config import TelemetryConfig
from .emitter import TelemetryEmitter
from .event_factory import TelemetryEventFactory

logger = logging.getLogger("logger")


class TelemetryReporter:
    """Coordinates telemetry reporting for a single request.

    Single responsibility: given a request outcome, build the event (factory) and
    hand it to the transport (emitter). Holds no Flask/HTTP knowledge itself.
    """

    def __init__(
        self,
        config: TelemetryConfig,
        factory: TelemetryEventFactory,
        emitter: TelemetryEmitter,
    ) -> None:
        self._config = config
        self._factory = factory
        self._emitter = emitter

    def report(
        self,
        endpoint: str,
        duration_ms: int,
        success: bool,
        error_code: Optional[str] = None,
        user_sub: Optional[str] = None,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> None:
        if not self._config.enabled:
            return
        payload = self._factory.create(
            endpoint=endpoint,
            duration_ms=duration_ms,
            success=success,
            error_code=error_code,
            user_sub=user_sub,
            project_id=project_id,
            identity_mode=self._config.identity_mode,
        )
        self._emitter.emit(payload, session_id=session_id)


def build_default_reporter() -> TelemetryReporter:
    """Factory wiring the default telemetry reporter from the environment."""
    config = TelemetryConfig()
    return TelemetryReporter(
        config=config,
        factory=TelemetryEventFactory(),
        emitter=TelemetryEmitter(config),
    )
