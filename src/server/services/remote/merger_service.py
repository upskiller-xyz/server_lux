
import logging

from ...enums import EndpointType, ServiceName
from .base import RemoteService
from .contracts import MergerRequest

logger = logging.getLogger('logger')


class MergerService(RemoteService):
    """Service for merging multiple window simulations"""
    name: ServiceName = ServiceName.MERGER

    @classmethod
    def _get_request(cls, endpoint: EndpointType) -> type[MergerRequest]:
        """Return the request class for this service"""
        return MergerRequest