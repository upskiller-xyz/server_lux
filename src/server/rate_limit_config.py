import os
from dataclasses import dataclass
from typing import Optional


# Defaults kept as named constants so no magic numbers/strings leak into the code.
DEFAULT_LIMIT_PER_DAY = 10
# Generous ceiling for the supporting compute endpoints (obstruction/encode/stats
# …). A normal simulation makes several of these calls, so this must comfortably
# exceed DEFAULT_LIMIT_PER_DAY × (calls per run); it only exists to stop hammering.
DEFAULT_AUX_LIMIT_PER_DAY = 300
# Rolling window length. A user gets `limit` requests per this many hours; the
# window is a fixed span that starts at their first request (Redis key TTL), not
# a calendar day — so there is no midnight boundary to double up on.
DEFAULT_WINDOW_HOURS = 24
DEFAULT_KEY_PREFIX = "lux:quota"

SECONDS_PER_HOUR = 3600


@dataclass(frozen=True)
class RateLimitConfig:
    """Immutable rate-limit configuration, built from environment variables."""

    enabled: bool
    limit: int
    redis_url: Optional[str]
    key_prefix: str
    # Length of the rolling window (hours); the counter's TTL.
    window_hours: int = DEFAULT_WINDOW_HOURS
    # Ceiling for the supporting compute endpoints (own bucket, separate from the
    # prediction limit). 0 ⇒ don't guard the auxiliary endpoints.
    aux_limit: int = DEFAULT_AUX_LIMIT_PER_DAY
    # When set, the quota applies ONLY to this Auth0 client (the web app's client
    # id / `azp`). Other clients (e.g. the Revit add-in) stay unlimited even on the
    # same endpoint. Empty ⇒ apply to every authenticated caller.
    client_id: Optional[str] = None
    # Number of reverse proxies (load balancer, CDN, …) in front of the app that
    # append to X-Forwarded-For. 0 ⇒ the header is untrusted (client-spoofable) and
    # the IP fallback uses the socket's remote_addr instead. Only raise this to
    # match the actual proxy chain depth.
    trusted_proxy_hops: int = 0

    @classmethod
    def from_environment(cls) -> "RateLimitConfig":
        """Build config from env vars.

        - ``RATE_LIMIT_ENABLED``    ("true"/"false", default "false")
        - ``RATE_LIMIT_PER_DAY``    (int, default 10)
        - ``RATE_LIMIT_AUX_PER_DAY``(int, default 300; 0 = don't guard aux endpoints)
        - ``RATE_LIMIT_WINDOW_HOURS``(int, default 24; the rolling window / TTL)
        - ``RATE_LIMIT_REDIS_URL``  (falls back to ``REDIS_URL``)
        - ``RATE_LIMIT_KEY_PREFIX`` (default "lux:quota")
        - ``RATE_LIMIT_CLIENT_ID``  (Auth0 client id the limit applies to; empty = all)
        - ``RATE_LIMIT_TRUSTED_PROXY_HOPS`` (int, default 0; number of reverse
          proxies appending to X-Forwarded-For — 0 = don't trust the header)
        """
        enabled = os.getenv("RATE_LIMIT_ENABLED", "false").strip().lower() == "true"
        limit = int(os.getenv("RATE_LIMIT_PER_DAY", str(DEFAULT_LIMIT_PER_DAY)))
        aux_limit = int(os.getenv("RATE_LIMIT_AUX_PER_DAY", str(DEFAULT_AUX_LIMIT_PER_DAY)))
        window_hours = int(os.getenv("RATE_LIMIT_WINDOW_HOURS", str(DEFAULT_WINDOW_HOURS)))
        redis_url = os.getenv("RATE_LIMIT_REDIS_URL") or os.getenv("REDIS_URL") or None
        key_prefix = os.getenv("RATE_LIMIT_KEY_PREFIX", DEFAULT_KEY_PREFIX)
        client_id = os.getenv("RATE_LIMIT_CLIENT_ID") or None
        trusted_proxy_hops = int(os.getenv("RATE_LIMIT_TRUSTED_PROXY_HOPS", "0"))
        return cls(
            enabled=enabled,
            limit=limit,
            redis_url=redis_url,
            key_prefix=key_prefix,
            window_hours=window_hours,
            aux_limit=aux_limit,
            client_id=client_id,
            trusted_proxy_hops=trusted_proxy_hops,
        )

    @property
    def window_seconds(self) -> int:
        """The rolling window / TTL in seconds."""
        return self.window_hours * SECONDS_PER_HOUR
