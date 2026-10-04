"""Unit tests for the trial guard.

These use the in-memory store and a Flask test app so no Redis is required.
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from flask import Flask, g, jsonify

from src.server.enums import (
    AuthContextKey,
    ErrorType,
    HTTPHeader,
    HTTPStatus,
    ResponseKey,
)
from src.server.trial_config import TrialConfig
from src.server.trial_guard import TrialGuard
from src.server.trial_store import (
    InMemoryTrialStore,
    NullTrialStore,
    TrialState,
    TrialStore,
)

TRIAL_CLIENT = "lux-revit-trial"
PAID_CLIENT = "lux-revit-paid"


def _config(enabled: bool = True, client_id: str | None = TRIAL_CLIENT, hours: int = 168) -> TrialConfig:
    return TrialConfig(
        enabled=enabled,
        client_id=client_id,
        hours=hours,
        redis_url=None,
        key_prefix="test:trial",
    )


def _guard(config: TrialConfig | None = None, store: TrialStore | None = None) -> TrialGuard:
    return TrialGuard(config or _config(), store or InMemoryTrialStore("test:trial"))


def _app_with_route(
    guard: TrialGuard,
    client_id: str | None = None,
    domain: str | None = None,
    guard_status_route: bool = False,
) -> Flask:
    app = Flask(__name__)

    @app.route("/run")
    @guard.require_trial
    def run():
        return jsonify({ResponseKey.STATUS.value: "ok"})

    @app.route("/trial/status")
    def trial_status():
        # Mirrors main.py composition: authentication only — get_status()
        # performs the trial lookup itself so an expired trial is reported
        # instead of rejected. Set guard_status_route=True to verify the
        # miscomposition is caught.
        if guard_status_route:
            return guard.require_trial(guard.get_status)()
        return guard.get_status()

    @app.before_request
    def _set_identity():
        if client_id is not None:
            setattr(g, AuthContextKey.CLIENT_ID.value, client_id)
        if domain is not None:
            setattr(g, AuthContextKey.DOMAIN.value, domain)

    return app


def test_first_trial_request_starts_the_clock_and_sets_headers():
    client = _app_with_route(_guard(), client_id=TRIAL_CLIENT, domain="foretagx.se").test_client()

    response = client.get("/run")
    assert response.status_code == HTTPStatus.OK.value
    assert HTTPHeader.TRIAL_STARTED_AT.value in response.headers
    assert HTTPHeader.TRIAL_EXPIRES_AT.value in response.headers
    assert response.get_json()[ResponseKey.STATUS.value] == "ok"


def test_deadline_is_fixed_after_first_request():
    guard = _guard(_config(hours=1))
    client = _app_with_route(guard, client_id=TRIAL_CLIENT, domain="foretagx.se").test_client()

    first = client.get("/run")
    second = client.get("/run")
    # A second request must not move the deadline — the window is fixed.
    assert (
        first.headers[HTTPHeader.TRIAL_EXPIRES_AT.value]
        == second.headers[HTTPHeader.TRIAL_EXPIRES_AT.value]
    )


def test_trial_is_per_domain():
    store = InMemoryTrialStore("test:trial")
    guard = _guard(store=store)
    x = _app_with_route(guard, client_id=TRIAL_CLIENT, domain="foretagx.se").test_client()
    y = _app_with_route(guard, client_id=TRIAL_CLIENT, domain="foretagy.se").test_client()

    first = x.get("/run")
    other = y.get("/run")
    assert (
        first.headers[HTTPHeader.TRIAL_EXPIRES_AT.value]
        != other.headers[HTTPHeader.TRIAL_EXPIRES_AT.value]
    )


def test_expired_trial_is_blocked():
    guard = _guard(store=_ExpiredTrialStore())
    client = _app_with_route(guard, client_id=TRIAL_CLIENT, domain="foretagx.se").test_client()

    response = client.get("/run")
    assert response.status_code == HTTPStatus.FORBIDDEN.value
    body = response.get_json()
    assert body[ResponseKey.ERROR_TYPE.value] == ErrorType.TRIAL_EXPIRED.value
    assert ResponseKey.TRIAL_STARTED_AT.value in body
    assert ResponseKey.TRIAL_EXPIRES_AT.value in body
    assert HTTPHeader.TRIAL_EXPIRES_AT.value in response.headers


def test_missing_domain_claim_fails_closed():
    # Trial token without the domain claim → blocked, not exempted.
    guard = _guard()
    client = _app_with_route(guard, client_id=TRIAL_CLIENT, domain=None).test_client()

    response = client.get("/run")
    assert response.status_code == HTTPStatus.FORBIDDEN.value
    assert response.get_json()[ResponseKey.ERROR_TYPE.value] == ErrorType.TRIAL_DOMAIN_MISSING.value


def test_paying_customers_pass_through():
    # Any other client id is exempt from the trial guard entirely.
    guard = _guard()
    client = _app_with_route(guard, client_id=PAID_CLIENT, domain=None).test_client()

    response = client.get("/run")
    assert response.status_code == HTTPStatus.OK.value
    assert HTTPHeader.TRIAL_EXPIRES_AT.value not in response.headers


def test_unidentifiable_caller_passes_through():
    # No azp at all (e.g. token auth) → not a trial caller → untouched.
    guard = _guard()
    client = _app_with_route(guard, client_id=None, domain=None).test_client()

    assert client.get("/run").status_code == HTTPStatus.OK.value


def test_disabled_guard_is_a_passthrough():
    guard = _guard(_config(enabled=False), NullTrialStore())
    client = _app_with_route(guard, client_id=TRIAL_CLIENT, domain="foretagx.se").test_client()

    response = client.get("/run")
    assert response.status_code == HTTPStatus.OK.value
    assert HTTPHeader.TRIAL_EXPIRES_AT.value not in response.headers


def test_store_error_fails_closed_for_trial_callers():
    guard = _guard(store=_FailingTrialStore())
    client = _app_with_route(guard, client_id=TRIAL_CLIENT, domain="foretagx.se").test_client()

    response = client.get("/run")
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE.value
    assert (
        response.get_json()[ResponseKey.ERROR_TYPE.value]
        == ErrorType.TRIAL_STORE_UNAVAILABLE.value
    )


def test_enabled_config_requires_client_id():
    # TRIAL_ENABLED=true without TRIAL_CLIENT_ID must refuse to construct —
    # silently guarding nothing would fail open with unrestricted access.
    env = {"TRIAL_ENABLED": "true"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="TRIAL_CLIENT_ID"):
            TrialConfig.from_environment()


def test_status_endpoint_reports_without_blocking():
    guard = _guard()
    client = _app_with_route(guard, client_id=TRIAL_CLIENT, domain="foretagx.se").test_client()

    status = client.get("/trial/status")
    assert status.status_code == HTTPStatus.OK.value
    body = status.get_json()
    assert body[ResponseKey.STATUS.value] == "active"
    assert body[ResponseKey.TRIAL_STARTED_AT.value]
    assert body[ResponseKey.TRIAL_EXPIRES_AT.value]
    assert body[ResponseKey.REMAINING_HOURS.value] > 0


def test_status_endpoint_reports_expired_not_rejects():
    # The real route composition: authentication only, no require_trial wrap —
    # an expired trial must be REPORTED, not 403:ed before get_status runs.
    guard = _guard(store=_ExpiredTrialStore())
    client = _app_with_route(guard, client_id=TRIAL_CLIENT, domain="foretagx.se").test_client()

    status = client.get("/trial/status")
    assert status.status_code == HTTPStatus.OK.value
    body = status.get_json()
    assert body[ResponseKey.STATUS.value] == "expired"
    assert body[ResponseKey.TRIAL_EXPIRES_AT.value]


def test_status_route_wrapped_in_guard_would_block_expired():
    # Regression proof for the composition bug: wrapping the status route in
    # require_trial rejects an expired trial before it can report itself.
    guard = _guard(store=_ExpiredTrialStore())
    client = _app_with_route(
        guard, client_id=TRIAL_CLIENT, domain="foretagx.se", guard_status_route=True
    ).test_client()

    status = client.get("/trial/status")
    assert status.status_code == HTTPStatus.FORBIDDEN.value
    assert status.get_json()[ResponseKey.ERROR_TYPE.value] == ErrorType.TRIAL_EXPIRED.value


def test_status_not_applicable_for_other_clients():
    guard = _guard()
    client = _app_with_route(guard, client_id=PAID_CLIENT, domain=None).test_client()

    status = client.get("/trial/status")
    assert status.status_code == HTTPStatus.OK.value
    assert status.get_json()[ResponseKey.STATUS.value] == "not_applicable"


class _ExpiredTrialStore(TrialStore):
    """A store whose every window is already in the past."""

    def activate_or_get(self, domain: str, duration_seconds: int) -> TrialState:
        started = datetime.now(timezone.utc) - timedelta(seconds=duration_seconds + 3600)
        expires = started + timedelta(seconds=duration_seconds)
        return TrialState(domain=domain, started_at=started, expires_at=expires)


class _FailingTrialStore(TrialStore):
    """A store whose backend is unavailable."""

    def activate_or_get(self, domain: str, duration_seconds: int) -> TrialState:
        raise RuntimeError("redis down")