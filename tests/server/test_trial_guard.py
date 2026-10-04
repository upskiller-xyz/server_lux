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
    AuthType,
    ErrorType,
    HTTPHeader,
    HTTPStatus,
    ResponseKey,
    TrialStatus,
)
from src.server.trial_config import TrialConfig, TrialDomain
from src.server.trial_guard import TrialGuard
from src.server.trial_store import (
    InMemoryTrialStore,
    NullTrialStore,
    RedisTrialStore,
    TrialKeyBuilder,
    TrialState,
    TrialStore,
    TrialStoreFactory,
)

TRIAL_CLIENT = "lux-revit-trial"
PAID_CLIENT = "lux-revit-paid"
FAKE_REDIS_URL = "redis://redis:6379"
TEST_PREFIX = "test:trial"
TEST_DOMAIN = "foretagx.se"


def _config(enabled: bool = True, client_id: str | None = TRIAL_CLIENT, hours: int = 168) -> TrialConfig:
    return TrialConfig(
        enabled=enabled,
        client_id=client_id,
        hours=hours,
        redis_url=None,
        key_prefix="test:trial",
    )


def _guard(config: TrialConfig | None = None, store: TrialStore | None = None) -> TrialGuard:
    resolved = config or _config()
    # The store owns the window length, so it is built from the same config
    # the guard reads — exactly as TrialStoreFactory does in production.
    return TrialGuard(resolved, store or InMemoryTrialStore("test:trial", resolved.duration_seconds))


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
    store = InMemoryTrialStore("test:trial", 168 * 3600)
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
    env = {"TRIAL_ENABLED": "true", "AUTH_TYPE": AuthType.AUTH0.value}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="TRIAL_CLIENT_ID"):
            TrialConfig.from_environment()


def test_status_endpoint_reports_without_blocking():
    guard = _guard()
    client = _app_with_route(guard, client_id=TRIAL_CLIENT, domain="foretagx.se").test_client()

    client.get("/run")  # activates the window
    status = client.get("/trial/status")
    assert status.status_code == HTTPStatus.OK.value
    body = status.get_json()
    assert body[ResponseKey.STATUS.value] == TrialStatus.ACTIVE.value
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
    assert body[ResponseKey.STATUS.value] == TrialStatus.EXPIRED.value
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
    assert status.get_json()[ResponseKey.STATUS.value] == TrialStatus.NOT_APPLICABLE.value


class _ExpiredTrialStore(TrialStore):
    """A store whose every window is already in the past."""

    EXPIRED_HOURS = 1
    DURATION_SECONDS = 168 * 3600

    def activate_or_get(self, domain: str) -> TrialState:
        started = datetime.now(timezone.utc) - timedelta(
            seconds=self.DURATION_SECONDS + self.EXPIRED_HOURS * 3600
        )
        expires = started + timedelta(seconds=self.DURATION_SECONDS)
        return TrialState(domain=domain, started_at=started, expires_at=expires)

    def get(self, domain: str) -> TrialState:
        # The window exists, it is simply over — distinct from "not started".
        return self.activate_or_get(domain)


class _FailingTrialStore(TrialStore):
    """A store whose backend is unavailable."""

    def activate_or_get(self, domain: str) -> TrialState:
        raise RuntimeError("redis down")

    def get(self, domain: str) -> TrialState:
        raise RuntimeError("redis down")

def test_status_does_not_start_the_clock():
    # A plugin polling status on startup must not burn trial time: the window
    # only starts on a real guarded request.
    store = InMemoryTrialStore("test:trial", 168 * 3600)
    guard = _guard(store=store)
    client = _app_with_route(guard, client_id=TRIAL_CLIENT, domain="foretagx.se").test_client()

    body = client.get("/trial/status").get_json()
    assert body[ResponseKey.STATUS.value] == TrialStatus.NOT_STARTED.value
    assert store.get("foretagx.se") is None
    # The full window is still ahead of them.
    assert body[ResponseKey.REMAINING_HOURS.value] == 168


def test_status_reports_remaining_hours_of_the_running_window():
    guard = _guard(_config(hours=10))
    client = _app_with_route(guard, client_id=TRIAL_CLIENT, domain="foretagx.se").test_client()

    client.get("/run")
    body = client.get("/trial/status").get_json()
    assert body[ResponseKey.STATUS.value] == TrialStatus.ACTIVE.value
    assert 9 < body[ResponseKey.REMAINING_HOURS.value] <= 10


def test_enabled_config_requires_auth0():
    # The guard matches on the Auth0 `azp` claim, which token auth never sets —
    # an enabled trial there would protect nothing. Refuse to start.
    env = {
        "TRIAL_ENABLED": "true",
        "TRIAL_CLIENT_ID": TRIAL_CLIENT,
        "AUTH_TYPE": AuthType.TOKEN.value,
        "TRIAL_REDIS_URL": FAKE_REDIS_URL,
    }
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="AUTH_TYPE"):
            TrialConfig.from_environment()


def test_enabled_config_rejects_non_positive_hours():
    env = {
        "TRIAL_ENABLED": "true",
        "TRIAL_CLIENT_ID": TRIAL_CLIENT,
        "AUTH_TYPE": AuthType.AUTH0.value,
        "TRIAL_REDIS_URL": FAKE_REDIS_URL,
        "TRIAL_HOURS": "0",
    }
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="TRIAL_HOURS"):
            TrialConfig.from_environment()


def test_valid_environment_builds_config():
    env = {
        "TRIAL_ENABLED": "true",
        "TRIAL_CLIENT_ID": TRIAL_CLIENT,
        "AUTH_TYPE": AuthType.AUTH0.value,
        "TRIAL_REDIS_URL": FAKE_REDIS_URL,
        "TRIAL_HOURS": "48",
    }
    with patch.dict(os.environ, env, clear=True):
        config = TrialConfig.from_environment()
    assert config.enabled is True
    assert config.client_id == TRIAL_CLIENT
    assert config.duration_seconds == 48 * 3600


class _FakeRedis:
    """Minimal Redis stand-in: the SET/GET/NX and pipeline semantics the trial
    store relies on, so the NX-pair logic is covered without a server."""

    def __init__(self):
        self.store: dict = {}

    def set(self, key, value, nx: bool = False):
        if nx and key in self.store:
            return False
        self.store[key] = str(value)
        return True

    def get(self, key):
        return self.store.get(key)

    def pipeline(self):
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, client: _FakeRedis):
        self._client = client
        self._queued: list = []

    def set(self, key, value, nx: bool = False):
        self._queued.append(lambda: self._client.set(key, value, nx=nx))
        return self

    def get(self, key):
        self._queued.append(lambda: self._client.get(key))
        return self

    def execute(self):
        results = [op() for op in self._queued]
        self._queued = []
        return results


class TestRedisTrialStore:
    """The shared store's atomic NX-pair behaviour and its repair path."""

    HOUR = 3600

    def test_first_call_activates_and_second_call_reads_the_same_window(self):
        store = RedisTrialStore(_FakeRedis(), "test:trial", self.HOUR)

        first = store.activate_or_get("foretagx.se")
        second = store.activate_or_get("foretagx.se")

        assert first == second
        assert not first.is_expired

    def test_changed_duration_does_not_move_an_active_window(self):
        # TRIAL_HOURS raised after activation. The length now lives on the
        # store, so the restart is modelled as a second store over the same
        # Redis — the running window must not grow with it.
        client = _FakeRedis()
        store = RedisTrialStore(client, "test:trial", self.HOUR)
        restarted = RedisTrialStore(client, "test:trial", 100 * self.HOUR)

        original = store.activate_or_get("foretagx.se")
        later = restarted.activate_or_get("foretagx.se")

        assert later.expires_at == original.expires_at
        assert later.started_at == original.started_at

    def test_lost_started_key_does_not_hand_out_a_new_window(self):
        # Item 14: repairing the bookkeeping half must never overwrite a live
        # deadline — that would reset an expired company's trial.
        client = _FakeRedis()
        store = RedisTrialStore(client, "test:trial", self.HOUR)
        original = store.activate_or_get("foretagx.se")
        del client.store[TrialKeyBuilder(TEST_PREFIX).started("foretagx.se")]

        repaired = store.activate_or_get("foretagx.se")

        assert repaired.expires_at == original.expires_at
        assert repaired.started_at == original.started_at
        assert client.store[TrialKeyBuilder(TEST_PREFIX).started("foretagx.se")]

    def test_lost_deadline_key_restarts_the_window(self):
        # The deadline is the canonical key; losing it genuinely loses the
        # trial, and the pair is restored whole.
        client = _FakeRedis()
        store = RedisTrialStore(client, "test:trial", self.HOUR)
        store.activate_or_get("foretagx.se")
        client.store.clear()

        restored = store.activate_or_get("foretagx.se")

        assert not restored.is_expired
        keys = TrialKeyBuilder(TEST_PREFIX)
        assert keys.deadline("foretagx.se") in client.store
        assert keys.started("foretagx.se") in client.store

    def test_get_is_a_pure_read(self):
        client = _FakeRedis()
        store = RedisTrialStore(client, "test:trial", self.HOUR)

        assert store.get("foretagx.se") is None
        assert client.store == {}

        store.activate_or_get("foretagx.se")
        assert store.get("foretagx.se").expires_at

    def test_get_is_keyed_per_domain(self):
        store = RedisTrialStore(_FakeRedis(), "test:trial", self.HOUR)

        store.activate_or_get("foretagx.se")

        assert store.get("foretagy.se") is None


class TestTrialDomainValidation:
    """The domain claim is stamped by an Auth0 Action — outside this codebase —
    and becomes part of a Redis key, so the guard validates it rather than
    trusting it."""

    @pytest.mark.parametrize("raw,expected", [
        ("foretagx.se", "foretagx.se"),
        ("FORETAGX.SE", "foretagx.se"),          # normalised to lower case
        ("  foretagx.se  ", "foretagx.se"),      # trimmed
        ("foretagx.se.", "foretagx.se"),         # trailing root dot dropped
        ("sub.foretagx.co.uk", "sub.foretagx.co.uk"),
        ("my-company.se", "my-company.se"),
    ])
    def test_valid_domains_are_normalised(self, raw, expected):
        assert TrialDomain.normalise(raw) == expected

    @pytest.mark.parametrize("raw", [
        None, "", "   ",
        "foretagx.se:started",      # the key separator — see the collision test
        "foretagx",                 # no TLD: not a company domain
        "foretagx..se",             # empty label
        "-foretagx.se",             # label may not start with a hyphen
        "foretagx-.se",             # or end with one
        "foretag x.se",             # whitespace
        "foretagx.se\nX-Injected: 1",
        "foretagx.se/../../etc",
        "*.foretagx.se",
        "a" * 254 + ".se",          # over the RFC 1035 length limit
        "x" * 64 + ".se",           # label over 63 characters
    ])
    def test_invalid_domains_are_rejected(self, raw):
        assert TrialDomain.normalise(raw) is None

    def test_invalid_domain_claim_fails_closed_on_a_guarded_route(self):
        # A claim that is not a hostname must be rejected, not normalised into
        # something that happens to work.
        guard = _guard()
        client = _app_with_route(
            guard, client_id=TRIAL_CLIENT, domain="foretagx.se:started"
        ).test_client()

        response = client.get("/run")
        assert response.status_code == HTTPStatus.FORBIDDEN.value
        assert (
            response.get_json()[ResponseKey.ERROR_TYPE.value]
            == ErrorType.TRIAL_DOMAIN_MISSING.value
        )

    def test_key_namespaces_cannot_collide(self):
        # Regression proof: with the old suffix layout, the deadline key of
        # "<domain>:started" WAS the started key of "<domain>". The domain is now
        # always the last segment, so no domain can address another's keys.
        keys = TrialKeyBuilder(TEST_PREFIX)
        assert keys.deadline("foretagx.se:started") != keys.started("foretagx.se")
        assert keys.deadline(TEST_DOMAIN) != keys.started(TEST_DOMAIN)
        # The domain is the trailing segment of both keys.
        assert keys.deadline(TEST_DOMAIN).endswith(TEST_DOMAIN)
        assert keys.started(TEST_DOMAIN).endswith(TEST_DOMAIN)


class TestSharedStoreRequirement:
    """An enabled trial with a process-local store is the control failing open:
    one clock per gunicorn worker, reset on every restart."""

    BASE_ENV = {
        "TRIAL_ENABLED": "true",
        "TRIAL_CLIENT_ID": TRIAL_CLIENT,
        "AUTH_TYPE": AuthType.AUTH0.value,
    }

    def test_enabled_without_a_shared_store_refuses_to_start(self):
        with patch.dict(os.environ, self.BASE_ENV, clear=True):
            with pytest.raises(ValueError, match="TRIAL_REDIS_URL"):
                TrialConfig.from_environment()

    def test_plain_redis_url_satisfies_the_requirement(self):
        env = dict(self.BASE_ENV, REDIS_URL=FAKE_REDIS_URL)
        with patch.dict(os.environ, env, clear=True):
            assert TrialConfig.from_environment().redis_url == FAKE_REDIS_URL

    def test_local_store_requires_an_explicit_opt_in(self):
        env = dict(self.BASE_ENV, TRIAL_ALLOW_LOCAL_STORE="true")
        with patch.dict(os.environ, env, clear=True):
            config = TrialConfig.from_environment()
        assert config.allow_local_store is True
        assert config.redis_url is None
        # And that opt-in is what the factory's in-memory fallback now needs.
        assert isinstance(TrialStoreFactory().create(config), InMemoryTrialStore)

    def test_disabled_trial_needs_no_store(self):
        with patch.dict(os.environ, {"TRIAL_ENABLED": "false"}, clear=True):
            assert TrialConfig.from_environment().enabled is False


class TestReviewFindings:
    """Regressions for the findings raised on the hardening PR."""

    HOUR = 3600

    def test_claim_that_is_not_a_string_is_rejected(self):
        # JWT custom claims are arbitrary JSON. A numeric or list claim must
        # fail closed, not raise on .strip() and surface as a 500.
        for claim in (42, 3.5, ["foretagx.se"], {"domain": "foretagx.se"}, True):
            assert TrialDomain.normalise(claim) is None

    def test_one_root_dot_is_trimmed_and_further_dots_are_rejected(self):
        # A single trailing dot is the DNS root and is legitimate; more than
        # one is malformed and must not be normalised into a working domain.
        assert TrialDomain.normalise("foretagx.se.") == "foretagx.se"
        assert TrialDomain.normalise("foretagx.se..") is None
        assert TrialDomain.normalise("foretagx.se...") is None

    def test_lost_started_key_is_derived_from_the_deadline_not_the_clock(self):
        # Arrange: an old window whose bookkeeping half is gone. The deadline
        # is the only surviving truth, so the start must be derived from it —
        # writing the current time would report a window starting after it ends.
        client = _FakeRedis()
        store = RedisTrialStore(client, TEST_PREFIX, self.HOUR)
        keys = TrialKeyBuilder(TEST_PREFIX)
        store.activate_or_get("foretagx.se")
        expired_deadline = int(datetime.now(timezone.utc).timestamp()) - 10 * self.HOUR
        client.store[keys.deadline("foretagx.se")] = str(expired_deadline)
        del client.store[keys.started("foretagx.se")]

        # Act
        repaired = store.activate_or_get("foretagx.se")

        # Assert
        assert int(repaired.expires_at.timestamp()) == expired_deadline
        assert int(repaired.started_at.timestamp()) == expired_deadline - self.HOUR
        assert repaired.started_at < repaired.expires_at
        assert repaired.is_expired

    def test_disabled_trial_tolerates_a_nonpositive_window(self):
        # TRIAL_HOURS is only a misconfiguration when something reads it; a
        # disabled deployment must not refuse to start over it.
        with patch.dict(os.environ, {"TRIAL_ENABLED": "false", "TRIAL_HOURS": "0"}, clear=True):
            assert TrialConfig.from_environment().enabled is False

    def test_get_derives_a_lost_start_instead_of_reporting_the_deadline(self):
        # Arrange: a live window whose bookkeeping half is gone. The pure read
        # has no activation to repair it, so it must derive the start from the
        # deadline and its own window length — reporting the deadline itself
        # would claim a window that starts when it ends.
        client = _FakeRedis()
        store = RedisTrialStore(client, TEST_PREFIX, self.HOUR)
        keys = TrialKeyBuilder(TEST_PREFIX)
        store.activate_or_get("foretagx.se")
        deadline = int(client.store[keys.deadline("foretagx.se")])
        del client.store[keys.started("foretagx.se")]

        # Act
        state = store.get("foretagx.se")

        # Assert
        assert int(state.expires_at.timestamp()) == deadline
        assert int(state.started_at.timestamp()) == deadline - self.HOUR
        assert state.started_at < state.expires_at
        # And the read stayed pure: nothing was written back.
        assert keys.started("foretagx.se") not in client.store
