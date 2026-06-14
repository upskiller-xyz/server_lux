"""Lightweight stage timing for latency investigation.

Use as a context manager to log how long a named stage took. Logs at INFO with a
``[timing]`` prefix so it is greppable without enabling DEBUG.

    with StageTimer("extract_params", logger):
        params = parse(request)
"""
import logging
import time
from types import TracebackType
from typing import Optional, Type


class StageTimer:
    """Logs the wall time of a named stage on exit (always, even on exception)."""

    def __init__(self, stage: str, logger: logging.Logger):
        self._stage = stage
        self._logger = logger
        self._t0 = 0.0

    def __enter__(self) -> "StageTimer":
        self._t0 = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> bool:
        elapsed_ms = (time.perf_counter() - self._t0) * 1000
        self._logger.info(f"[timing] {self._stage}: {elapsed_ms:.0f}ms")
        return False  # never suppress exceptions
