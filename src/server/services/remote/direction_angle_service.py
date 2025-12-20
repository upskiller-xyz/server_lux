from typing import Any, Dict

from .contracts import RemoteServiceRequest, DirectionAngleRequest
from .contracts import DirectionAngleResponse
from ...enums import ServiceName, EndpointType
from .base import RemoteService


class DirectionAngleService(RemoteService):
    """Service for calculating window direction angles

    Handles /calculate-direction endpoint.
    Follows Single Responsibility Principle - only calculates direction angles.
    """
    name: ServiceName = ServiceName.ENCODER  # Uses encoder microservice

    @classmethod
    def _get_request(cls, endpoint: EndpointType) -> type[RemoteServiceRequest]:
        """Get request class for endpoint"""
        return DirectionAngleRequest

    @classmethod
    def _get_response(cls, endpoint: EndpointType) -> type[DirectionAngleResponse]:
        """Get response class for endpoint"""
        return DirectionAngleResponse

    @classmethod
    def run(cls, endpoint: EndpointType, request: RemoteServiceRequest, file: Any = None) -> Dict[str, Any]:
        """Calculate direction angles for windows"""
        response_class = cls._get_response(endpoint)
        return super().run(endpoint, request, file, response_class)
