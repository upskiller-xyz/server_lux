"""Unit tests for the best-effort GPU prewarm (ModelPrewarmer)."""

import pytest

from src.server.constants import ModalBackend
from src.server.services.remote import model_prewarmer
from src.server.services.remote.model_prewarmer import ModelPrewarmer


class _FakeThread:
    """Records construction instead of spawning a real thread."""
    instances: list["_FakeThread"] = []

    def __init__(self, target=None, args=(), daemon=None):
        self.target, self.args, self.daemon = target, args, daemon
        self.started = False
        _FakeThread.instances.append(self)

    def start(self) -> None:
        self.started = True


@pytest.fixture(autouse=True)
def _no_threads(monkeypatch):
    _FakeThread.instances = []
    monkeypatch.setattr(model_prewarmer.threading, "Thread", _FakeThread)


class TestPrewarmGating:

    def test_container_backend_is_noop(self, monkeypatch):
        # A container/VM URL has no cold start to hide → no thread spawned.
        monkeypatch.setenv("MODEL_SERVICE_URL", "http://model-service:8083")
        ModelPrewarmer.prewarm()
        assert _FakeThread.instances == []

    def test_modal_backend_spawns_daemon_warm_ping(self, monkeypatch):
        monkeypatch.setenv(
            "MODEL_SERVICE_URL",
            "https://acme--upskiller-model-inferenceservice-web.modal.run",
        )
        ModelPrewarmer.prewarm()
        assert len(_FakeThread.instances) == 1
        thread = _FakeThread.instances[0]
        assert thread.daemon is True
        assert thread.started is True
        assert thread.args[0].endswith("/warm")


class TestPrewarmNeverRaises:

    def test_config_failure_is_swallowed(self, monkeypatch):
        def boom():
            raise RuntimeError("config unavailable")
        monkeypatch.setattr(model_prewarmer, "get_service_config", boom)
        ModelPrewarmer.prewarm()  # must not raise
        assert _FakeThread.instances == []

    def test_ping_swallows_missing_credentials(self, monkeypatch):
        # _ping resolves Modal auth headers, which raise when creds are missing —
        # the prewarm is best-effort and must swallow it.
        monkeypatch.delenv(ModalBackend.KEY_ENV, raising=False)
        monkeypatch.delenv(ModalBackend.SECRET_ENV, raising=False)
        ModelPrewarmer._ping("https://x.modal.run/warm")  # must not raise

    def test_ping_swallows_network_errors(self, monkeypatch):
        monkeypatch.setenv(ModalBackend.KEY_ENV, "wk-abc")
        monkeypatch.setenv(ModalBackend.SECRET_ENV, "ws-def")

        def boom(*args, **kwargs):
            raise Exception("network down")
        monkeypatch.setattr(model_prewarmer.requests, "get", boom)
        ModelPrewarmer._ping("https://x.modal.run/warm")  # must not raise
