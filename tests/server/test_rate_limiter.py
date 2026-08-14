"""Unit tests for the rolling-window rate limiter.

These use the in-memory store and a Flask test app so no Redis is required.
"""

from datetime import datetime, timezone

from flask import Flask, g, jsonify

from src.server.enums import ErrorType, HTTPStatus, ResponseKey
from src.server.rate_limit_config import RateLimitConfig
from src.server.rate_limit_store import (
    InMemoryRateLimitStore,
    NullRateLimitStore,
    QuotaState,
)
from src.server.rate_limiter import (
    AUTH_CLIENT_ID_KEY,
    AUTH_SUBJECT_KEY,
    HEADER_REMAINING,
    RateLimiter,
    RequestIdentityResolver,
)


def _config(enabled: bool = True, limit: int = 3, client_id: str | None = None) -> RateLimitConfig:
    return RateLimitConfig(
        enabled=enabled,
        limit=limit,
        redis_url=None,
        key_prefix="test:quota",
        client_id=client_id,
    )


def _store() -> InMemoryRateLimitStore:
    return InMemoryRateLimitStore("test:quota")


def _app_with_route(limiter: RateLimiter, subject: str | None, client_id: str | None = None) -> Flask:
    app = Flask(__name__)

    @app.route("/simulate")
    @limiter.require_quota
    def simulate():
        return jsonify({ResponseKey.STATUS.value: "ok"})

    @app.route("/obstruction")
    @limiter.require_aux_quota
    def obstruction():
        return jsonify({ResponseKey.STATUS.value: "ok"})

    @app.before_request
    def _set_identity():
        if subject is not None:
            setattr(g, AUTH_SUBJECT_KEY, subject)
        if client_id is not None:
            setattr(g, AUTH_CLIENT_ID_KEY, client_id)

    return app


def test_allows_up_to_the_limit_then_blocks():
    limiter = RateLimiter(_config(limit=3), _store())
    app = _app_with_route(limiter, subject="auth0|alice")
    client = app.test_client()

    for expected_remaining in (2, 1, 0):
        response = client.get("/simulate")
        assert response.status_code == HTTPStatus.OK.value
        assert response.headers[HEADER_REMAINING] == str(expected_remaining)

    blocked = client.get("/simulate")
    assert blocked.status_code == HTTPStatus.TOO_MANY_REQUESTS.value
    body = blocked.get_json()
    assert body[ResponseKey.ERROR_TYPE.value] == ErrorType.RATE_LIMIT_EXCEEDED.value
    assert body[ResponseKey.REMAINING.value] == 0
    assert ResponseKey.RESET_AT.value in body


def test_quota_is_per_subject():
    limiter = RateLimiter(_config(limit=1), _store())
    alice = _app_with_route(limiter, subject="auth0|alice").test_client()
    bob = _app_with_route(limiter, subject="auth0|bob").test_client()

    assert alice.get("/simulate").status_code == HTTPStatus.OK.value
    assert alice.get("/simulate").status_code == HTTPStatus.TOO_MANY_REQUESTS.value
    # Bob shares the limiter/store but has his own bucket.
    assert bob.get("/simulate").status_code == HTTPStatus.OK.value


def test_quota_only_applies_to_configured_client():
    # Limit only the web app's client id; other clients (e.g. Revit) pass through.
    limiter = RateLimiter(_config(limit=1, client_id="lux-web"), _store())

    web = _app_with_route(limiter, subject="auth0|alice", client_id="lux-web").test_client()
    assert web.get("/simulate").status_code == HTTPStatus.OK.value
    assert web.get("/simulate").status_code == HTTPStatus.TOO_MANY_REQUESTS.value

    revit = _app_with_route(limiter, subject="auth0|alice", client_id="lux-revit").test_client()
    for _ in range(5):
        assert revit.get("/simulate").status_code == HTTPStatus.OK.value


def test_prediction_and_aux_have_separate_budgets():
    # limit=1 prediction, aux_limit=2: the buckets are independent counters.
    config = RateLimitConfig(
        enabled=True, limit=1, redis_url=None,
        key_prefix="test:quota", aux_limit=2,
    )
    client = _app_with_route(RateLimiter(config, _store()), subject="auth0|alice").test_client()

    # One prediction allowed, second blocked.
    assert client.get("/simulate").status_code == HTTPStatus.OK.value
    assert client.get("/simulate").status_code == HTTPStatus.TOO_MANY_REQUESTS.value
    # Aux bucket untouched by predictions: its own limit of 2 still applies.
    assert client.get("/obstruction").status_code == HTTPStatus.OK.value
    assert client.get("/obstruction").status_code == HTTPStatus.OK.value
    assert client.get("/obstruction").status_code == HTTPStatus.TOO_MANY_REQUESTS.value


def test_aux_guard_off_when_aux_limit_zero():
    config = RateLimitConfig(
        enabled=True, limit=1, redis_url=None,
        key_prefix="test:quota", aux_limit=0,
    )
    client = _app_with_route(RateLimiter(config, _store()), subject="auth0|alice").test_client()
    for _ in range(5):
        assert client.get("/obstruction").status_code == HTTPStatus.OK.value


def test_disabled_limiter_is_a_passthrough():
    limiter = RateLimiter(_config(enabled=False), NullRateLimitStore())
    client = _app_with_route(limiter, subject="auth0|alice").test_client()

    for _ in range(5):
        assert client.get("/simulate").status_code == HTTPStatus.OK.value


def test_falls_back_to_ip_without_subject():
    limiter = RateLimiter(_config(limit=1), _store())
    app = _app_with_route(limiter, subject=None)
    client = app.test_client()

    first = client.get("/simulate", environ_overrides={"REMOTE_ADDR": "1.2.3.4"})
    assert first.status_code == HTTPStatus.OK.value
    second = client.get("/simulate", environ_overrides={"REMOTE_ADDR": "1.2.3.4"})
    assert second.status_code == HTTPStatus.TOO_MANY_REQUESTS.value


def test_identity_prefers_subject_over_ip():
    resolver = RequestIdentityResolver()
    app = Flask(__name__)
    with app.test_request_context("/", environ_overrides={"REMOTE_ADDR": "9.9.9.9"}):
        setattr(g, AUTH_SUBJECT_KEY, "auth0|carol")
        assert resolver.resolve() == "sub:auth0|carol"


def test_window_resets_after_ttl_elapses():
    # A 1-second window: after it elapses, the count starts over.
    store = _store()
    config = RateLimitConfig(enabled=True, limit=1, redis_url=None, key_prefix="test:quota", window_hours=1)
    # Drive the store directly with a tiny window_seconds to avoid sleeping.
    assert store.hit("pred:sub:x", limit=1, window_seconds=0).used == 1
    # window_seconds=0 ⇒ the previous window is already elapsed on the next hit.
    assert store.hit("pred:sub:x", limit=1, window_seconds=0).used == 1
    # A live window keeps counting up.
    assert store.hit("pred:sub:y", limit=2, window_seconds=3600).used == 1
    assert store.hit("pred:sub:y", limit=2, window_seconds=3600).used == 2
    assert config.window_seconds == 3600


def test_reset_at_is_in_the_future():
    state = _store().hit("pred:sub:z", limit=5, window_seconds=3600)
    assert state.reset_at > datetime.now(timezone.utc)


def test_quota_state_flags():
    reset = datetime.now(timezone.utc)
    assert QuotaState(limit=10, used=10, reset_at=reset).exceeded is False
    assert QuotaState(limit=10, used=11, reset_at=reset).remaining == 0
    assert QuotaState(limit=10, used=3, reset_at=reset).remaining == 7
