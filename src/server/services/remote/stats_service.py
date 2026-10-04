
from ...enums import EndpointType, ServiceName
from .base import RemoteService
from .contracts import StatsRequest


class StatsService(RemoteService):
    """Service for calculating statistics on daylight factor data"""
    name: ServiceName = ServiceName.STATS

    @classmethod
    def _get_request(cls, endpoint: EndpointType) -> type[StatsRequest]:
        """Get request class for stats endpoint"""
        return StatsRequest

