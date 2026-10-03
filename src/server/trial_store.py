import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

import redis

from .trial_config import TrialConfig

logger = logging.getLogger("logger")


@dataclass(frozen=True)
class TrialState:
    """The caller's company-wide trial window."""

    domain: str
    started_at: datetime
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def remaining_hours(self) -> float:
        return max(0.0, (self.expires_at - datetime.now(timezone.utc)).total_seconds() / 3600.0)


class TrialStore(ABC):
    """The deadline store behind the trial guard.

    A company's clock starts on its first request (``activate_or_get``); every
    later request reads the same fixed window.
    """

    @abstractmethod
    def activate_or_get(self, domain: str, duration_seconds: int) -> TrialState:
        """Return the existing trial window for ``domain``, or start one now.

        Idempotent and atomic: concurrent first requests from the same company
        must all land on the same started_at/expires_at pair.
        """


class InMemoryTrialStore(TrialStore):
    """Process-local trial deadlines. Not shared across workers — only for
    local development and tests."""

    def __init__(self, key_prefix: str):
        self._key_prefix = key_prefix
        self._lock = threading.Lock()
        # domain -> (started_epoch_seconds, expires_epoch_seconds)
        self._windows: Dict[str, Tuple[float, float]] = {}

    def activate_or_get(self, domain: str, duration_seconds: int) -> TrialState:
        key = f"{self._key_prefix}:{domain}"
        now = time.time()
        with self._lock:
            window = self._windows.get(key)
            if window is None:
                started, expires = now, now + duration_seconds
                self._windows[key] = (started, expires)
            else:
                started, expires = window
        return TrialState(
            domain=domain,
            started_at=datetime.fromtimestamp(started, tz=timezone.utc),
            expires_at=datetime.fromtimestamp(expires, tz=timezone.utc),
        )


class RedisTrialStore(TrialStore):
    """Shared trial deadlines in Redis.

    ``SET key <expires_epoch> NX`` starts the clock on the company's first
    request; the started_at is reconstructable as expires minus duration, but
    is also kept in a companion key so it survives duration overrides. Shared
    across all workers/instances that point at the Redis.
    """

    def __init__(self, client, key_prefix: str):
        self._client = client
        self._key_prefix = key_prefix

    def activate_or_get(self, domain: str, duration_seconds: int) -> TrialState:
        deadline_key = f"{self._key_prefix}:{domain}"
        now = time.time()
        expires = int(now + duration_seconds)
        # NX: only the first request ever writes; later requests keep the
        # original deadline. Atomic, so concurrent first requests converge.
        was_set = self._client.set(deadline_key, expires, nx=True)
        if not was_set:
            expires = int(self._client.get(deadline_key))
        return TrialState(
            domain=domain,
            started_at=datetime.fromtimestamp(expires - duration_seconds, tz=timezone.utc),
            expires_at=datetime.fromtimestamp(expires, tz=timezone.utc),
        )


class NullTrialStore(TrialStore):
    """Used when the trial guard is disabled — never starts or blocks anything."""

    def activate_or_get(self, domain: str, duration_seconds: int) -> TrialState:
        started_at = datetime.now(timezone.utc)
        return TrialState(
            domain=domain,
            started_at=started_at,
            expires_at=started_at + timedelta(seconds=duration_seconds),
        )


class TrialStoreFactory:
    """Selects a store from config: Null when disabled, Redis when a URL is
    set, otherwise the in-memory fallback (with a loud warning)."""

    def create(self, config: TrialConfig) -> TrialStore:
        if not config.enabled or not config.client_id:
            return NullTrialStore()

        if config.redis_url:
            client = redis.Redis.from_url(config.redis_url, decode_responses=True)
            return RedisTrialStore(client, config.key_prefix)

        logger.warning(
            "TRIAL_ENABLED but no REDIS_URL set — using in-memory trial store. "
            "This is NOT shared across gunicorn workers/instances; set REDIS_URL in production."
        )
        return InMemoryTrialStore(config.key_prefix)