import os
import re
from dataclasses import dataclass
from typing import Optional

from .enums import AuthType
from .env_keys import EnvKey

# Defaults kept as named constants so no magic numbers/strings leak into the code.
# A one-week trial: 168 hours from the company's first request.
DEFAULT_TRIAL_HOURS = 168
DEFAULT_TRIAL_KEY_PREFIX = "lux:trial"

SECONDS_PER_HOUR = 3600


class TrialDomain:
    """Validates and normalises the company domain claim before it is used.

    The claim is stamped by an Auth0 Action — outside this codebase — and is
    then used to build the Redis keys the trial window lives under. Treating it
    as trusted would make the key layout's safety depend on an invariant
    enforced somewhere else: a domain carrying the key separator could address
    another company's keys. So it is validated here, at the boundary, and an
    unparseable domain is rejected (fail closed) rather than normalised into
    something that happens to work.
    """

    MAX_LENGTH = 253          # RFC 1035 limit on a fully-qualified name
    MAX_LABEL_LENGTH = 63
    LABEL_SEPARATOR = "."
    # A label: alphanumeric at both ends, hyphens allowed inside. Deliberately
    # excludes ":" (the key separator), whitespace and every other character.
    LABEL_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")

    @classmethod
    def normalise(cls, raw: Optional[str]) -> Optional[str]:
        """Lower-cased, trimmed domain — or None if it is not a valid hostname.

        None means "cannot be attributed to a company", which the guard turns
        into a rejection; it never falls through to an unguarded request.
        """
        if not isinstance(raw, str) or not raw:
            # JWT custom claims are arbitrary JSON: a numeric or list claim must
            # be rejected here, not raise on .strip() and become a 500.
            return None
        domain = raw.strip().lower()
        if domain.endswith(cls.LABEL_SEPARATOR):
            # At most one DNS root dot. Any further trailing dot stays as an
            # empty label and is rejected below, so "example.se.." cannot be
            # normalised into something that happens to work.
            domain = domain[:-1]
        if not domain or len(domain) > cls.MAX_LENGTH:
            return None
        labels = domain.split(cls.LABEL_SEPARATOR)
        if len(labels) < 2:
            # A company domain always has a TLD; a bare label is not one.
            return None
        for label in labels:
            if not label or len(label) > cls.MAX_LABEL_LENGTH:
                return None
            if not cls.LABEL_PATTERN.match(label):
                return None
        return domain


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
    # Opt-in for the process-local store. The trial is a per-company control, so
    # a store that is not shared across workers does not implement it; this must
    # be stated explicitly (local development) rather than fallen back into.
    allow_local_store: bool = False

    @classmethod
    def from_environment(cls) -> "TrialConfig":
        """Build config from env vars.

        - ``TRIAL_ENABLED``     ("true"/"false", default "false")
        - ``TRIAL_CLIENT_ID``   (Auth0 client id the trial applies to; required)
        - ``TRIAL_HOURS``       (int, default 168 — one week)
        - ``TRIAL_REDIS_URL``   (falls back to ``REDIS_URL``)
        - ``TRIAL_KEY_PREFIX``  (default "lux:trial")
        - ``TRIAL_ALLOW_LOCAL_STORE`` ("true" to accept the process-local store)

        Raises:
            ValueError: if the trial is enabled but cannot possibly apply — no
                client id, a non-positive window, an ``AUTH_TYPE`` that never
                yields the ``azp`` the guard matches on, or no shared deadline
                store to enforce the window with.
        """
        enabled = os.getenv(EnvKey.TRIAL_ENABLED.value, "false").strip().lower() == "true"
        client_id = os.getenv(EnvKey.TRIAL_CLIENT_ID.value) or None
        allow_local_store = (
            os.getenv(EnvKey.TRIAL_ALLOW_LOCAL_STORE.value, "false").strip().lower() == "true"
        )
        if enabled:
            if client_id is None:
                # Fail closed at startup: an enabled trial without a client id
                # would silently guard nothing (fail-open), granting unrestricted
                # access. Refuse to start instead — same policy as AuthConfig.
                raise ValueError("TRIAL_ENABLED=true requires TRIAL_CLIENT_ID to be set")
            cls._require_auth0()
            cls._require_shared_store(redis_url_present=bool(
                os.getenv(EnvKey.TRIAL_REDIS_URL.value) or os.getenv(EnvKey.REDIS_URL.value)
            ), allow_local=allow_local_store)
        hours = int(os.getenv(EnvKey.TRIAL_HOURS.value, str(DEFAULT_TRIAL_HOURS)))
        if enabled and hours <= 0:
            # A non-positive window expires every trial caller on contact —
            # almost certainly a misconfiguration, not an intent to block. Only
            # checked when the trial is on: a disabled deployment must not fail
            # to start over a setting nothing reads.
            raise ValueError("TRIAL_HOURS must be a positive number of hours")
        redis_url = os.getenv(EnvKey.TRIAL_REDIS_URL.value) or os.getenv(EnvKey.REDIS_URL.value) or None
        key_prefix = os.getenv(EnvKey.TRIAL_KEY_PREFIX.value, DEFAULT_TRIAL_KEY_PREFIX)
        return cls(
            enabled=enabled,
            client_id=client_id,
            hours=hours,
            redis_url=redis_url,
            key_prefix=key_prefix,
            allow_local_store=allow_local_store,
        )

    @staticmethod
    def _require_auth0() -> None:
        """Refuse an enabled trial under an auth mode that cannot support it.

        The guard matches callers on the ``azp`` claim, which only the Auth0
        strategy puts on the request. Under token/no auth the guard would
        therefore match nobody and silently protect nothing — the same
        fail-open the TRIAL_CLIENT_ID check exists to prevent, so it is
        refused at startup rather than logged as "enabled".
        """
        auth_type = os.getenv(EnvKey.AUTH_TYPE.value, AuthType.TOKEN.value).strip().lower()
        if auth_type != AuthType.AUTH0.value:
            raise ValueError(
                "TRIAL_ENABLED=true requires AUTH_TYPE={expected} (the trial keys on the "
                "Auth0 `azp` claim); AUTH_TYPE is currently '{actual}'".format(
                    expected=AuthType.AUTH0.value, actual=auth_type
                )
            )

    @staticmethod
    def _require_shared_store(redis_url_present: bool, allow_local: bool) -> None:
        """Refuse an enabled trial with no store to enforce it with.

        The process-local store is not shared across gunicorn workers, so each
        worker would start its own clock: one company silently gets as many
        trials as there are workers, and every restart resets them. That is the
        control failing open while the startup log says "enabled" — the same
        thing the client-id and AUTH_TYPE checks exist to prevent — so it has to
        be asked for deliberately instead of fallen back into.
        """
        if redis_url_present or allow_local:
            return
        raise ValueError(
            "TRIAL_ENABLED=true requires {redis} (or {fallback}) — the "
            "process-local store is not shared across workers and cannot "
            "enforce a company-wide trial".format(
                redis=EnvKey.TRIAL_REDIS_URL.value,
                fallback=EnvKey.TRIAL_ALLOW_LOCAL_STORE.value,
            )
        )

    @property
    def duration_seconds(self) -> int:
        """Trial length in seconds.

        Not a key TTL: the Redis store deliberately keeps the deadline key
        forever and compares it to the clock, so an expired company cannot be
        handed a fresh window by the key quietly disappearing.
        """
        return self.hours * SECONDS_PER_HOUR