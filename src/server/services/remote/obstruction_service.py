from typing import Dict, Any
from ...interfaces.remote_interfaces import ObstructionRequest, ObstructionResponse
from ...enums import ServiceName, EndpointType
from .base import RemoteService


class ObstructionService(RemoteService):
    """Service for obstruction angle calculations"""
    name: ServiceName = ServiceName.OBSTRUCTION

    @classmethod
    def run(cls, endpoint: EndpointType, x: float, y: float, z: float, rad_x: float, rad_y: float, mesh: list, http_client, base_url: str) -> Dict[str, Any]:
        """Calculate obstruction angles"""
        request = ObstructionRequest(x=x, y=y, z=z, rad_x=rad_x, rad_y=rad_y, mesh=mesh)
        return super().run(endpoint, request, ObstructionResponse, http_client, base_url)
