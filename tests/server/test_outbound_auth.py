"""Unit tests for URL-driven outbound auth (Modal proxy-auth)."""

import pytest

from src.server.constants import ModalBackend
from src.server.enums import ServiceBackend, ModalAuthHeader
from src.server.exceptions import ModalCredentialsError
from src.server.services.remote.outbound_auth import (
    BackendResolver,
    NoOutboundAuth,
    ModalProxyAuth,
    BackendAuthMap,
)


class TestBackendResolver:

    @pytest.mark.parametrize("url", [
        "https://acme--upskiller-model-inferenceservice-web.modal.run",
        "https://acme--upskiller-model-inferenceservice-web.modal.run/run",
        "http://x.MODAL.RUN/spec",
    ])
    def test_modal_hosts_resolve_to_modal(self, url):
        assert BackendResolver.resolve(url) == ServiceBackend.MODAL

    @pytest.mark.parametrize("url", [
        "http://51.15.197.220:8083/run",
        "http://localhost:8083",
        "https://model-server-123.europe-north2.run.app/run",
        "https://notmodal.run.example.com",
    ])
    def test_non_modal_hosts_resolve_to_container(self, url):
        assert BackendResolver.resolve(url) == ServiceBackend.CONTAINER


class TestModalProxyAuth:

    def test_headers_returns_both_proxy_auth_headers(self, monkeypatch):
        monkeypatch.setenv(ModalBackend.KEY_ENV, "wk-abc")
        monkeypatch.setenv(ModalBackend.SECRET_ENV, "ws-def")
        headers = ModalProxyAuth().headers()
        assert headers == {
            ModalAuthHeader.KEY.value: "wk-abc",
            ModalAuthHeader.SECRET.value: "ws-def",
        }

    def test_missing_both_credentials_raises(self, monkeypatch):
        monkeypatch.delenv(ModalBackend.KEY_ENV, raising=False)
        monkeypatch.delenv(ModalBackend.SECRET_ENV, raising=False)
        with pytest.raises(ModalCredentialsError) as exc:
            ModalProxyAuth().headers()
        assert ModalBackend.KEY_ENV in exc.value.missing
        assert ModalBackend.SECRET_ENV in exc.value.missing

    def test_missing_one_credential_raises(self, monkeypatch):
        monkeypatch.setenv(ModalBackend.KEY_ENV, "wk-abc")
        monkeypatch.delenv(ModalBackend.SECRET_ENV, raising=False)
        with pytest.raises(ModalCredentialsError) as exc:
            ModalProxyAuth().headers()
        assert exc.value.missing == [ModalBackend.SECRET_ENV]


class TestNoOutboundAuth:

    def test_returns_empty(self):
        assert NoOutboundAuth().headers() == {}


class TestBackendAuthMap:

    def test_container_maps_to_no_auth(self):
        assert isinstance(BackendAuthMap.get(ServiceBackend.CONTAINER), NoOutboundAuth)

    def test_modal_maps_to_modal_proxy_auth(self):
        assert isinstance(BackendAuthMap.get(ServiceBackend.MODAL), ModalProxyAuth)
