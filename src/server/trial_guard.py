import logging
from functools import wraps
from typing import Any, Callable, Optional

from flask import g, jsonify, make_response

from .enums import ErrorType, HTTPHeader, ResponseKey
from .rate_limiter import AUTH_CLIENT_ID_KEY
from .response_builder import ErrorResponseBuilder
from .trial_config import TrialConfig
from .trial_store import NullTrialStore, TrialState, TrialStore, TrialStoreFactory

logger = logging.getLogger("logger")

# flask.g attribute the Auth0 strategy sets from the validated token's custom
# trial-domain claim.
AUTH_DOMAIN_KEY = "auth_domain"
AUTH_CLIENT_ID_KEY = "auth_client_id"  # Auth0 `azp` (authorized party = client id)


class TrialGuard:
    """Company-wide time-limited trial, applied as a route decorator.

    Only requests from the trial Auth0 client (``TRIAL_CLIENT_ID``) are guarded;
    every other client (paying Revit customers, the web app) passes through
    untouched. The company is identified by the domain claim the trial login
    Action stamps on the token — a missing claim fails closed: an unidentifiable
    trial caller is blocked, not exempted.
    """

    def __init__(
        self,
        config: TrialConfig,
        store: TrialStore,
    ):
        self._config = config
        self._store = store
        self._error_builder = ErrorResponseBuilder()

    @classmethod
    def from_environment(cls) -> "TrialGuard":
        config = TrialConfig.from_environment()
        store = TrialStoreFactory().create(config)
        return cls(config, store)

    @property
    def is_enabled(self) -> bool:
        return self._config.enabled and self._config.client_id is not None

    def require_trial(self, f: Callable) -> Callable:
        """Decorate a route so trial-client callers are time-limited. No-op
        for every other caller, and when the trial is disabled."""
        @wraps(f)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            if not self._applies_to_caller():
                return f(*args, **kwargs)
            domain = getattr(g, AUTH_DOMAIN_KEY, None)
            if not domain:
                # Fail closed: the trial Action must stamp the domain claim —
                # a token without it cannot be attributed to a company, so it
                # gets no trial window.
                return self._reject(ErrorType.TRIAL_DOMAIN_MISSING)
            try:
                state = self._store.activate_or_get(domain, self._config.duration_seconds)
            except Exception as exc:
                # A store outage must not take the server down; failing closed
                # here is safe because it only affects trial callers, never
                # paying customers. The distinct error type tells the plugin
                # this is transient and retryable, not a missing registration.
                logger.error("Trial store error — blocking trial request (fail-closed): %s", exc)
                return self._reject(ErrorType.TRIAL_STORE_UNAVAILABLE)
            if state.is_expired:
                return self._reject(ErrorType.TRIAL_EXPIRED, state)
            response = make_response(f(*args, **kwargs))
            self._apply_headers(response, state)
            return response

        return decorated

    def get_status(self) -> Any:
        """Read-only trial status for the caller (GET /v1/trial/status).

        Starts the clock on first call like any guarded request, but never
        blocks: an expired trial is reported, not rejected, so the client can
        render "expired" without guessing. Not wrapped in require_trial —
        the guard decorator would 403 an expired trial before this could
        report it. Only authentication applies on the route.
        """
        if not self._applies_to_caller():
            return jsonify({ResponseKey.STATUS.value: "not_applicable"})
        domain = getattr(g, AUTH_DOMAIN_KEY, None)
        if not domain:
            return self._reject(ErrorType.TRIAL_DOMAIN_MISSING)
        try:
            state = self._store.activate_or_get(domain, self._config.duration_seconds)
        except Exception as exc:
            logger.error("Trial store error — blocking trial status (fail-closed): %s", exc)
            return self._reject(ErrorType.TRIAL_STORE_UNAVAILABLE)
        payload = {
            ResponseKey.STATUS.value: "expired" if state.is_expired else "active",
            ResponseKey.TRIAL_STARTED_AT.value: state.started_at.isoformat(),
            ResponseKey.TRIAL_EXPIRES_AT.value: state.expires_at.isoformat(),
            ResponseKey.REMAINING_HOURS.value: round(state.remaining_hours, 1),
        }
        response = make_response(jsonify(payload))
        self._apply_headers(response, state)
        return response

    def _applies_to_caller(self) -> bool:
        """Whether the trial applies to the current request: only the
        configured trial client is guarded."""
        if not self._config.enabled or not self._config.client_id:
            return False
        azp = getattr(g, AUTH_CLIENT_ID_KEY, None)
        return azp == self._config.client_id

    def _reject(self, error_type: ErrorType, state: Optional[TrialState] = None):
        body, status = self._error_builder.build(error_type)
        payload = body.get_json()
        if state is not None:
            payload[ResponseKey.TRIAL_STARTED_AT.value] = state.started_at.isoformat()
            payload[ResponseKey.TRIAL_EXPIRES_AT.value] = state.expires_at.isoformat()
        response = make_response(jsonify(payload), status)
        if state is not None:
            self._apply_headers(response, state)
        return response

    def _apply_headers(self, response, state: TrialState) -> None:
        response.headers[HTTPHeader.TRIAL_STARTED_AT.value] = state.started_at.isoformat()
        response.headers[HTTPHeader.TRIAL_EXPIRES_AT.value] = state.expires_at.isoformat()