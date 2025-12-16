from typing import Dict, Any
import numpy as np
from ...interfaces.remote_interfaces import StatsRequest, StatsResponse
from ...enums import ServiceName, EndpointType
from .base import RemoteService


class StatsService(RemoteService):
    """Service for calculating statistics on daylight factor data"""
    name: ServiceName = ServiceName.STATS
    
