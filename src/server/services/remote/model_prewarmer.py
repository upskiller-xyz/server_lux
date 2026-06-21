"""Best-effort GPU prewarm — fire a fire-and-forget /warm ping at request entry.

When inference is on a scale-to-zero backend (Modal), the GPU cold start (~5-9s)
would otherwise be paid serially mid-pipeline (on the first /spec or /run call).
Pinging /warm as soon as an inference request arrives lets that cold start overlap
the CPU stages (encode etc.) instead of stacking on top of them.

No-op for always-on container/VM backends (no cold start to hide). Never raises —
warming is best-effort and must not affect the request. See
infra.lux/docs/experiments.md.
"""
import logging
import threading

import requests

from ...config import get_service_config
from ...enums import ServiceBackend, ServiceName
from .outbound_auth import BackendAuthMap, BackendResolver

logger = logging.getLogger("logger")


class ModelPrewarmer:
    """Triggers a non-blocking, single-in-flight warm of the model backend."""

    _WARM_PATH = "/warm"
    _TIMEOUT = 60  # > cold start; daemon thread never blocks the request

    # In-flight guard: only one warm ping runs at a time, so a burst of inference
    # requests can't pile up threads or flood the backend with redundant /warm calls.
    _lock = threading.Lock()
    _in_flight = False

    @classmethod
    def prewarm(cls) -> None:
        """Fire a fire-and-forget /warm ping iff the model is on a Modal backend and
        no warm ping is already running."""
        try:
            base_url = get_service_config().get_service_url(ServiceName.MODEL.value)
        except Exception:  # config lookup must never break the request
            return
        if BackendResolver.resolve(base_url) is not ServiceBackend.MODAL:
            return  # container/VM backend is always on — nothing to prewarm
        with cls._lock:
            if cls._in_flight:
                return  # a warm ping is already running — don't pile up threads
            cls._in_flight = True
        warm_url = f"{base_url}{cls._WARM_PATH}"
        logger.info(f"Prewarming model backend (fire-and-forget): {warm_url}")
        threading.Thread(target=cls._ping, args=(warm_url,), daemon=True).start()

    @classmethod
    def _ping(cls, warm_url: str) -> None:
        try:
            headers = BackendAuthMap.get(ServiceBackend.MODAL).headers()
            requests.get(warm_url, headers=headers, timeout=cls._TIMEOUT)
            logger.debug(f"Prewarm ping sent to {warm_url}")
        except Exception as e:  # best-effort — swallow everything (incl. missing creds)
            logger.debug(f"Prewarm ping failed (ignored): {e}")
        finally:
            with cls._lock:
                cls._in_flight = False
