from typing import Dict, Any
import numpy as np

from .contracts import StatsRequest
from .contracts import StatsResponse

from ...enums import ServiceName, EndpointType
from .base import RemoteService


class StatsService(RemoteService):
    """Service for calculating statistics on daylight factor data"""
    name: ServiceName = ServiceName.STATS

    @classmethod
    def _get_request(cls, endpoint: EndpointType) -> type[StatsRequest]:
        """Get request class for stats endpoint"""
        return StatsRequest

