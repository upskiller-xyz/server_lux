import os
from dataclasses import dataclass
from typing import Optional

# Defaults kept as named constants so no magic numbers/strings leak into the code.
# A one-week trial: 168 hours from the company's first request.
DEFAULT_TRIAL_HOURS = 168
DEFAULT_TRIAL_KEY_PREFIX = "lux:trial"

SECONDS_PER_HOUR = 3600


@dataclass(frozen=True)
class TrialConfig:
    """Immutable trial configuration, built from environment variables.

    The trial applies only to the Auth0 client configured as the trial client
    (``TRIAL_CLIENT_ID``); every other client (paying Revit customers, the web
    app) passes through untouched.
    """

    enabled: bool
    # Auth0 client id (``azp``) of the trial client. Requests from any other
    # client are exempt from the trial guard.
    client_id: Optional[str]
    # Trial length in hours, counted from the company's first request.
    hours: int
    redis_url: Optional[str]
    key_prefix: str

    @classmethod
    def from_environment(cls) -> "TrialConfig":
        """Build config from env vars.

        - ``TRIAL_ENABLED``     ("true"/"false", default "false")
        - ``TRIAL_CLIENT_ID``   (Auth0 client id the trial applies to; required)
        - ``TRIAL_HOURS``       (int, default 168 — one week)
        - ``TRIAL_REDIS_URL``   (falls back to ``REDIS_URL``)
        - ``TRIAL_KEY_PREFIX``  (default "lux:trial")
        """
        enabled = os.getenv("TRIAL_ENABLED", "false").strip().lower() == "true"
        client_id = os.getenv("TRIAL_CLIENT_ID") or None
        if enabled and client_id is None:
            # Fail closed at startup: an enabled trial without a client id
            # would silently guard nothing (fail-open), granting unrestricted
            # access. Refuse to start instead — same policy as AuthConfig.
            raise ValueError("TRIAL_ENABLED=true requires TRIAL_CLIENT_ID to be set")
        hours = int(os.getenv("TRIAL_HOURS", str(DEFAULT_TRIAL_HOURS)))
        redis_url = os.getenv("TRIAL_REDIS_URL") or os.getenv("REDIS_URL") or None
        key_prefix = os.getenv("TRIAL_KEY_PREFIX", DEFAULT_TRIAL_KEY_PREFIX)
        return cls(
            enabled=enabled,
            client_id=client_id,
            hours=hours,
            redis_url=redis_url,
            key_prefix=key_prefix,
        )

    @property
    def duration_seconds(self) -> int:
        """Trial length in seconds (the activation key's TTL)."""
        return self.hours * SECONDS_PER_HOUR