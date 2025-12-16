from typing import Dict, Any
from ...interfaces.remote_interfaces import MergerRequest, MergerResponse, WindowGeometry, Simulation
from ...enums import ServiceName, EndpointType
from .base import RemoteService
import logging

logger = logging.getLogger('logger')


class MergerService(RemoteService):
    """Service for merging multiple window simulations"""
    name: ServiceName = ServiceName.MERGER
    
    # @classmethod
    # def run(cls, room_polygon: list, windows: Dict[str, WindowGeometry], simulations: Dict[str, Simulation], http_client, base_url: str) -> Dict[str, Any]:
    #     """Merge window simulations into room-level result"""
    #     logger.info(f"Merging {len(windows)} window simulations for room")
    #     request = MergerRequest(room_polygon=room_polygon, windows=windows, simulations=simulations)
    #     return super().run(EndpointType.MERGE, request, MergerResponse, http_client, base_url)
