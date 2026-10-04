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


class TrialKeyBuilder:
    """Builds the Redis keys for one company's trial window.

    The two keys live in sibling namespaces (``<prefix>:deadline:<domain>`` and
    ``<prefix>:started:<domain>``) rather than one being a suffixed child of the
    other. With a suffix layout, a domain ending in the suffix would address the
    other key of a different company; here the domain is always the last
    segment, so no domain can reach another company's keys. The domain is
    validated by ``TrialDomain`` before it gets here — this layout means the key
    space stays unambiguous even if that validation is ever loosened.
    """

    KEY_TEMPLATE = "{prefix}:{kind}:{domain}"
    DEADLINE_KIND = "deadline"
    STARTED_KIND = "started"

    def __init__(self, key_prefix: str):
        self._key_prefix = key_prefix

    def deadline(self, domain: str) -> str:
        return self.KEY_TEMPLATE.format(
            prefix=self._key_prefix, kind=self.DEADLINE_KIND, domain=domain
        )

    def started(self, domain: str) -> str:
        return self.KEY_TEMPLATE.format(
            prefix=self._key_prefix, kind=self.STARTED_KIND, domain=domain
        )


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
    later request reads the same fixed window. ``get`` is the pure read used by
    the status endpoint, which must never start a clock.
    """

    @abstractmethod
    def activate_or_get(self, domain: str, duration_seconds: int) -> TrialState:
        """Return the existing trial window for ``domain``, or start one now.

        Idempotent and atomic: concurrent first requests from the same company
        must all land on the same started_at/expires_at pair.
        """

    @abstractmethod
    def get(self, domain: str) -> Optional[TrialState]:
        """Return ``domain``'s trial window, or None if it never started.

        A pure read: it must not create, extend or otherwise touch the window.
        """


class InMemoryTrialStore(TrialStore):
    """Process-local trial deadlines. Not shared across workers — only for
    local development and tests."""

    def __init__(self, key_prefix: str):
        self._keys = TrialKeyBuilder(key_prefix)
        self._lock = threading.Lock()
        # deadline key -> (started_epoch_seconds, expires_epoch_seconds)
        self._windows: Dict[str, Tuple[float, float]] = {}

    def activate_or_get(self, domain: str, duration_seconds: int) -> TrialState:
        key = self._keys.deadline(domain)
        now = time.time()
        with self._lock:
            window = self._windows.get(key)
            if window is None:
                started, expires = now, now + duration_seconds
                self._windows[key] = (started, expires)
            else:
                started, expires = window
        return self._state(domain, started, expires)

    def get(self, domain: str) -> Optional[TrialState]:
        with self._lock:
            window = self._windows.get(self._keys.deadline(domain))
        if window is None:
            return None
        return self._state(domain, *window)

    @staticmethod
    def _state(domain: str, started: float, expires: float) -> TrialState:
        return TrialState(
            domain=domain,
            started_at=datetime.fromtimestamp(started, tz=timezone.utc),
            expires_at=datetime.fromtimestamp(expires, tz=timezone.utc),
        )


class RedisTrialStore(TrialStore):
    """Shared trial deadlines in Redis.

    The company's first request atomically writes both the deadline and the
    original start timestamp (a single pipelined transaction), so a later
    change of ``TRIAL_HOURS`` cannot shift the reported start of an already
    activated trial. ``SET NX`` guarantees only the first request ever writes.
    Shared across all workers/instances that point at the Redis.

    Neither key gets a TTL: expiry is decided by comparing the stored deadline
    to the clock, never by the key disappearing. A TTL would silently hand an
    expired company a brand-new trial.
    """

    def __init__(self, client, key_prefix: str):
        self._client = client
        self._keys = TrialKeyBuilder(key_prefix)

    def activate_or_get(self, domain: str, duration_seconds: int) -> TrialState:
        deadline_key = self._keys.deadline(domain)
        started_key = self._keys.started(domain)
        now = int(time.time())
        # Read before writing. Writing both halves under NX up front looks
        # atomic but silently corrupts the one case that matters: with the
        # deadline alive and ``:started`` deleted, an NX write puts *now* in
        # the start slot, so the repair below never sees a gap and the window
        # is reported as starting after it ends.
        deadline_raw = self._client.get(deadline_key)
        if deadline_raw is None:
            # Not activated yet, or the deadline itself is gone. Write the pair
            # under NX so concurrent first requests converge on one writer, and
            # re-read rather than trusting our own candidate values.
            pipe = self._client.pipeline()
            pipe.set(deadline_key, now + duration_seconds, nx=True)
            pipe.set(started_key, now, nx=True)
            pipe.execute()
            deadline_raw = self._client.get(deadline_key)
            started_raw = self._client.get(started_key)
        else:
            # A live deadline is never touched — overwriting it would hand the
            # company a fresh window. Only the bookkeeping half may be
            # repaired, and only from the deadline it must stay consistent with.
            started_raw = self._client.get(started_key)
        if started_raw is None:
            started_raw = int(deadline_raw) - duration_seconds
            self._client.set(started_key, started_raw, nx=True)
        return self._state(domain, int(started_raw), int(deadline_raw))

    def get(self, domain: str) -> Optional[TrialState]:
        deadline_key = self._keys.deadline(domain)
        pipe = self._client.pipeline()
        pipe.get(deadline_key)
        pipe.get(self._keys.started(domain))
        deadline_raw, started_raw = pipe.execute()
        if deadline_raw is None:
            return None
        deadline = int(deadline_raw)
        # A missing ``:started`` must not hide an active window from the status
        # endpoint; fall back to the deadline as the best known start.
        started = int(started_raw) if started_raw is not None else deadline
        return self._state(domain, started, deadline)

    @staticmethod
    def _state(domain: str, started: int, expires: int) -> TrialState:
        return TrialState(
            domain=domain,
            started_at=datetime.fromtimestamp(started, tz=timezone.utc),
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

    def get(self, domain: str) -> Optional[TrialState]:
        return None


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
