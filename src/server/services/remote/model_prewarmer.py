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
    """Triggers a non-blocking warm of the model backend (Strategy via backend)."""

    _WARM_PATH = "/warm"
    # Longer than a cold start so the warm completes; runs in a daemon thread so it
    # never blocks the request regardless.
    _TIMEOUT = 60

    @classmethod
    def prewarm(cls) -> None:
        """Fire a fire-and-forget /warm ping iff the model is on a Modal backend."""
        try:
            base_url = get_service_config().get_service_url(ServiceName.MODEL.value)
        except Exception:  # config lookup must never break the request
            return
        if BackendResolver.resolve(base_url) is not ServiceBackend.MODAL:
            return  # container/VM backend is always on — nothing to prewarm
        threading.Thread(
            target=cls._ping,
            args=(f"{base_url}{cls._WARM_PATH}",),
            daemon=True,
        ).start()

    @classmethod
    def _ping(cls, warm_url: str) -> None:
        try:
            headers = BackendAuthMap.get(ServiceBackend.MODAL).headers()
            requests.get(warm_url, headers=headers, timeout=cls._TIMEOUT)
            logger.debug(f"Prewarm ping sent to {warm_url}")
        except Exception as e:  # best-effort — swallow everything (incl. missing creds)
            logger.debug(f"Prewarm ping failed (ignored): {e}")
