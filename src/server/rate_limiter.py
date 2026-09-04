import logging
from functools import wraps
from typing import Any, Callable, Optional

from flask import g, jsonify, make_response, request

logger = logging.getLogger("logger")

from .enums import ErrorType, ResponseKey
from .rate_limit_config import RateLimitConfig
from .rate_limit_store import QuotaState, RateLimitStore, RateLimitStoreFactory
from .response_builder import ErrorResponseBuilder

# flask.g attributes the authenticator sets from the validated token.
AUTH_SUBJECT_KEY = "auth_subject"
AUTH_CLIENT_ID_KEY = "auth_client_id"  # Auth0 `azp` (authorized party = client id)

# Standard rate-limit response headers (mirrors the IETF draft names).
HEADER_LIMIT = "X-RateLimit-Limit"
HEADER_REMAINING = "X-RateLimit-Remaining"
HEADER_RESET = "X-RateLimit-Reset"

# Separate daily buckets so a normal simulation's several supporting calls don't
# drain the prediction quota. Each keys its own Redis counter.
BUCKET_PREDICTION = "pred"
BUCKET_AUX = "aux"


class RequestIdentityResolver:
    """Derive the quota bucket for the current request.

    Prefers the authenticated subject (Auth0 ``sub``) so the limit follows the
    user across devices/IPs; falls back to the client IP when no subject is
    present (e.g. token auth), so a quota still applies.
    """

    def resolve(self) -> str:
        subject = getattr(g, AUTH_SUBJECT_KEY, None)
        if subject:
            return f"sub:{subject}"
        return f"ip:{self._client_ip()}"

    def _client_ip(self) -> str:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.remote_addr or "unknown"


class RateLimiter:
    """Per-identity daily quota, applied as a route decorator.

    Uses check-by-increment: the store atomically consumes one unit and the
    resulting count decides the verdict, so the limit holds across instances
    without a read-modify-write race.
    """

    def __init__(
        self,
        config: RateLimitConfig,
        store: RateLimitStore,
        identity_resolver: Optional[RequestIdentityResolver] = None,
    ):
        self._config = config
        self._store = store
        self._identity = identity_resolver or RequestIdentityResolver()
        self._error_builder = ErrorResponseBuilder()

    @classmethod
    def from_environment(cls) -> "RateLimiter":
        config = RateLimitConfig.from_environment()
        store = RateLimitStoreFactory().create(config)
        return cls(config, store)

    @property
    def is_enabled(self) -> bool:
        return self._config.enabled

    def require_quota(self, f: Callable) -> Callable:
        """Decorate a prediction route (/run, /simulate): one unit of the daily
        prediction quota per call. No-op when rate limiting is disabled."""
        return self._guard(f, self._config.limit, BUCKET_PREDICTION)

    def require_aux_quota(self, f: Callable) -> Callable:
        """Decorate a supporting compute route (obstruction/encode/stats/…): one
        unit of the separate, generous auxiliary ceiling per call. No-op when
        disabled or when the aux ceiling is 0."""
        return self._guard(f, self._config.aux_limit, BUCKET_AUX)

    def _guard(self, f: Callable, limit: int, bucket: str) -> Callable:
        if not self._config.enabled or limit <= 0:
            return f

        @wraps(f)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            if not self._applies_to_caller():
                return f(*args, **kwargs)  # e.g. the Revit add-in — unlimited
            identity = f"{bucket}:{self._identity.resolve()}"
            try:
                state = self._store.hit(identity, limit, self._config.window_seconds)
            except Exception as exc:
                # Fail OPEN: a Redis blip must not take down predictions. This is a
                # fair-use limit (cost/abuse), not a security control, so allowing
                # a request through during a store outage is the right trade-off.
                logger.warning("Rate-limit store error — allowing request (fail-open): %s", exc)
                return f(*args, **kwargs)
            if state.exceeded:
                return self._reject(state)
            response = make_response(f(*args, **kwargs))
            self._apply_headers(response, state)
            return response

        return decorated

    def _applies_to_caller(self) -> bool:
        """Whether the quota applies to the current request. When a client id is
        configured, the web app's client is limited and other *identified* clients
        (e.g. the Revit add-in) pass through. A caller we cannot identify (no `azp`)
        is limited — fail-safe, so a token without a client-id claim can't dodge
        the cap."""
        if not self._config.client_id:
            return True
        azp = getattr(g, AUTH_CLIENT_ID_KEY, None)
        if azp is None:
            return True  # unidentifiable caller → apply the limit, don't exempt
        return azp == self._config.client_id

    def _reject(self, state: QuotaState):
        body, status = self._error_builder.build(ErrorType.RATE_LIMIT_EXCEEDED)
        payload = body.get_json()
        payload[ResponseKey.LIMIT.value] = state.limit
        payload[ResponseKey.REMAINING.value] = state.remaining
        payload[ResponseKey.RESET_AT.value] = state.reset_at.isoformat()
        response = make_response(jsonify(payload), status)
        self._apply_headers(response, state)
        return response

    def _apply_headers(self, response, state: QuotaState) -> None:
        response.headers[HEADER_LIMIT] = str(state.limit)
        response.headers[HEADER_REMAINING] = str(state.remaining)
        response.headers[HEADER_RESET] = state.reset_at.isoformat()
