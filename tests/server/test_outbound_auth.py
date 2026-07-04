"""Unit tests for URL-driven outbound auth (Modal proxy-auth, Scaleway token)."""

import pytest

from src.server.constants import ModalBackend, ScalewayBackend
from src.server.enums import ServiceBackend, ModalAuthHeader, ScalewayAuthHeader
from src.server.exceptions import ModalCredentialsError, ScalewayCredentialsError
from src.server.services.remote.outbound_auth import (
    BackendResolver,
    NoOutboundAuth,
    ModalProxyAuth,
    ScalewayTokenAuth,
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

    @pytest.mark.parametrize("url", [
        "https://obstruction-abc.functions.fnc.fr-par.scw.cloud",
        "https://obstruction-abc.functions.fnc.fr-par.scw.cloud/obstruction_parallel_bin",
        "http://X.SCW.CLOUD/spec",
    ])
    def test_scaleway_hosts_resolve_to_scaleway(self, url):
        assert BackendResolver.resolve(url) == ServiceBackend.SCALEWAY


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


class TestScalewayTokenAuth:

    def test_headers_returns_token_header(self, monkeypatch):
        monkeypatch.setenv(ScalewayBackend.TOKEN_ENV, "tok-abc")
        headers = ScalewayTokenAuth().headers()
        assert headers == {ScalewayAuthHeader.TOKEN.value: "tok-abc"}

    def test_missing_token_raises(self, monkeypatch):
        monkeypatch.delenv(ScalewayBackend.TOKEN_ENV, raising=False)
        with pytest.raises(ScalewayCredentialsError) as exc:
            ScalewayTokenAuth().headers()
        assert exc.value.missing == [ScalewayBackend.TOKEN_ENV]


class TestNoOutboundAuth:

    def test_returns_empty(self):
        assert NoOutboundAuth().headers() == {}


class TestBackendAuthMap:

    def test_container_maps_to_no_auth(self):
        assert isinstance(BackendAuthMap.get(ServiceBackend.CONTAINER), NoOutboundAuth)

    def test_modal_maps_to_modal_proxy_auth(self):
        assert isinstance(BackendAuthMap.get(ServiceBackend.MODAL), ModalProxyAuth)

    def test_scaleway_maps_to_scaleway_token_auth(self):
        assert isinstance(BackendAuthMap.get(ServiceBackend.SCALEWAY), ScalewayTokenAuth)
