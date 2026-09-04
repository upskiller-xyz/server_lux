import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple

from .rate_limit_config import RateLimitConfig

logger = logging.getLogger("logger")


@dataclass(frozen=True)
class QuotaState:
    """A snapshot of one identity's quota after a single hit."""

    limit: int
    used: int
    reset_at: datetime

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    @property
    def exceeded(self) -> bool:
        # `used` counts the current request, so equality is still allowed.
        return self.used > self.limit


def _reset_at(seconds_from_now: int) -> datetime:
    """UTC timestamp `seconds_from_now` ahead — when the rolling window clears."""
    return datetime.now(timezone.utc) + timedelta(seconds=max(0, seconds_from_now))


class RateLimitStore(ABC):
    """Shared, atomic counter behind the rolling-window quota."""

    @abstractmethod
    def hit(self, identity: str, limit: int, window_seconds: int) -> QuotaState:
        """Consume one unit of ``identity``'s quota and return the new state. The
        window is a fixed span that starts on the first hit (a TTL)."""


class NullRateLimitStore(RateLimitStore):
    """Used when rate limiting is disabled — never consumes anything."""

    def hit(self, identity: str, limit: int, window_seconds: int) -> QuotaState:
        return QuotaState(limit=limit, used=0, reset_at=_reset_at(window_seconds))


class InMemoryRateLimitStore(RateLimitStore):
    """Process-local counter. Not shared across gunicorn workers/instances — only
    for local development and tests. The factory warns when it is chosen."""

    def __init__(self, key_prefix: str):
        self._key_prefix = key_prefix
        # identity -> (count, expiry_epoch_seconds)
        self._counts: Dict[str, Tuple[int, float]] = {}

    def hit(self, identity: str, limit: int, window_seconds: int) -> QuotaState:
        key = f"{self._key_prefix}:{identity}"
        now = time.time()
        count, expiry = self._counts.get(key, (0, 0.0))
        if now >= expiry:  # first hit, or the previous window has elapsed
            count, expiry = 0, now + window_seconds
        count += 1
        self._counts[key] = (count, expiry)
        return QuotaState(limit=limit, used=count, reset_at=_reset_at(int(expiry - now)))


class RedisRateLimitStore(RateLimitStore):
    """Atomic rolling-window counter in Redis: ``INCR`` plus a one-shot ``EXPIRE``
    set on the first hit, so the key self-clears ``window_seconds`` after that
    first request. Shared across all workers/instances that point at the Redis."""

    def __init__(self, client, key_prefix: str):
        self._client = client
        self._key_prefix = key_prefix

    def hit(self, identity: str, limit: int, window_seconds: int) -> QuotaState:
        key = f"{self._key_prefix}:{identity}"
        used = int(self._client.incr(key))
        if used == 1:
            self._client.expire(key, window_seconds)
            ttl = window_seconds
        else:
            ttl = self._client.ttl(key)
            if ttl < 0:  # no TTL somehow set — repair it so the key can't leak
                self._client.expire(key, window_seconds)
                ttl = window_seconds
        return QuotaState(limit=limit, used=used, reset_at=_reset_at(ttl))


class RateLimitStoreFactory:
    """Selects a store from config: Null when disabled, Redis when a URL is set,
    otherwise the in-memory fallback (with a loud warning)."""

    def create(self, config: RateLimitConfig) -> RateLimitStore:
        if not config.enabled:
            return NullRateLimitStore()

        if config.redis_url:
            import redis  # imported lazily so the dep is optional when disabled

            client = redis.Redis.from_url(config.redis_url, decode_responses=True)
            return RedisRateLimitStore(client, config.key_prefix)

        logger.warning(
            "RATE_LIMIT_ENABLED but no REDIS_URL set — using in-memory store. "
            "This is NOT shared across gunicorn workers/instances; set REDIS_URL in production."
        )
        return InMemoryRateLimitStore(config.key_prefix)
