"""Outbound authentication for remote service calls.

The backend hosting a service is inferred from its URL (Strategy/Adapter pattern):
a Modal-hosted endpoint (``*.modal.run``) requires proxy-auth headers, a container
endpoint does not. ``BackendResolver`` maps a URL to a :class:`ServiceBackend`, and
``BackendAuthMap`` maps that backend to the strategy producing the right headers.
"""
from abc import ABC, abstractmethod
from typing import Dict
from urllib.parse import urlparse
import os

from ...enums import ServiceBackend, ModalAuthHeader
from ...constants import ModalBackend
from ...exceptions import ModalCredentialsError
from ...maps import StandardMap


class BackendResolver:
    """Resolves the hosting backend of a service from its URL."""

    @staticmethod
    def resolve(url: str) -> ServiceBackend:
        host = (urlparse(url).hostname or "").lower()
        if host.endswith(ModalBackend.HOST_SUFFIX):
            return ServiceBackend.MODAL
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


class BackendAuthMap(StandardMap):
    """Maps a service backend to its outbound auth strategy."""
    _content: Dict[ServiceBackend, OutboundAuthStrategy] = {
        ServiceBackend.CONTAINER: NoOutboundAuth(),
        ServiceBackend.MODAL: ModalProxyAuth(),
    }
    _default: OutboundAuthStrategy = NoOutboundAuth()
