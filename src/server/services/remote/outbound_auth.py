"""Outbound authentication for remote service calls.

The backend hosting a service is inferred from its URL (Strategy/Adapter pattern):
a Modal-hosted endpoint (``*.modal.run``) requires proxy-auth headers, a private
Scaleway serverless endpoint (``*.scw.cloud``) requires the invocation token in
``X-Auth-Token``, and a plain container endpoint requires none. ``BackendResolver``
maps a URL to a :class:`ServiceBackend`, and ``BackendAuthMap`` maps that backend to
the strategy producing the right headers.
"""
from abc import ABC, abstractmethod
from typing import Dict
from urllib.parse import urlparse
import os

from ...enums import ServiceBackend, ModalAuthHeader, ScalewayAuthHeader
from ...constants import ModalBackend, ScalewayBackend
from ...exceptions import ModalCredentialsError, ScalewayCredentialsError
from ...maps import StandardMap


class BackendResolver:
    """Resolves the hosting backend of a service from its URL."""

    @staticmethod
    def resolve(url: str) -> ServiceBackend:
        host = (urlparse(url).hostname or "").lower()
        if host.endswith(ModalBackend.HOST_SUFFIX):
            return ServiceBackend.MODAL
        if host.endswith(ScalewayBackend.HOST_SUFFIX):
            return ServiceBackend.SCALEWAY
        return ServiceBackend.CONTAINER


class OutboundAuthStrategy(ABC):
    """Produces the auth headers to attach to an outgoing remote service call."""

    @abstractmethod
    def headers(self) -> Dict[str, str]:
        """Return auth headers for the request (empty if none required)."""
        pass


class NoOutboundAuth(OutboundAuthStrategy):
    """No outbound authentication (container/Cloud Run endpoints)."""

    def headers(self) -> Dict[str, str]:
        return {}


class ModalProxyAuth(OutboundAuthStrategy):
    """Modal proxy-auth: sends the proxy-auth token as Modal-Key / Modal-Secret.

    Credentials are read from the environment (MODAL_KEY / MODAL_SECRET). Raises
    :class:`ModalCredentialsError` when either is missing so the failure is clear
    before the request is made rather than surfacing as a remote 401.
    """

    def headers(self) -> Dict[str, str]:
        key = os.getenv(ModalBackend.KEY_ENV)
        secret = os.getenv(ModalBackend.SECRET_ENV)

        missing = [name for name, value in (
            (ModalBackend.KEY_ENV, key),
            (ModalBackend.SECRET_ENV, secret),
        ) if not value]
        if missing:
            raise ModalCredentialsError(missing)

        return {
            ModalAuthHeader.KEY.value: key,
            ModalAuthHeader.SECRET.value: secret,
        }


class ScalewayTokenAuth(OutboundAuthStrategy):
    """Scaleway serverless token auth: sends the invocation token in ``X-Auth-Token``.

    The token is read from the environment (SCW_CONTAINER_TOKEN). Raises
    :class:`ScalewayCredentialsError` when missing so the failure is clear before
    the request is made rather than surfacing as a remote 401/403.
    """

    def headers(self) -> Dict[str, str]:
        token = os.getenv(ScalewayBackend.TOKEN_ENV)
        if not token:
            raise ScalewayCredentialsError([ScalewayBackend.TOKEN_ENV])
        return {ScalewayAuthHeader.TOKEN.value: token}


class BackendAuthMap(StandardMap):
    """Maps a service backend to its outbound auth strategy."""
    _content: Dict[ServiceBackend, OutboundAuthStrategy] = {
        ServiceBackend.CONTAINER: NoOutboundAuth(),
        ServiceBackend.MODAL: ModalProxyAuth(),
        ServiceBackend.SCALEWAY: ScalewayTokenAuth(),
    }
    _default: OutboundAuthStrategy = NoOutboundAuth()
