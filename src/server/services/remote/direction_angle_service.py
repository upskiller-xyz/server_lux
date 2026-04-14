from typing import Any, Dict, List
import logging

from .contracts import RemoteServiceRequest, DirectionAngleRequest
from .contracts import DirectionAngleResponse
from ...enums import ServiceName, EndpointType
from .base import RemoteService

logger = logging.getLogger("logger")


class DirectionAngleService(RemoteService):
    """Service for calculating window direction angles

    Handles /calculate-direction endpoint.
    Follows Single Responsibility Principle - only calculates direction angles.
    Uses Enumerator Pattern - all string keys use RequestField/ResponseKey enums.
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
        """Calculate direction angles for windows
        
        Checks if windows already have direction_angle parameter.
        Uses pre-calculated angles where available, only computes missing ones.
        
        Args:
            endpoint: The endpoint to call
            request: The request object containing room_polygon and windows
            file: Optional file upload
            
        Returns:
            Dictionary with direction_angles for all windows
        """
        # Calculate missing angles via remote service
        response_class = cls._get_response(endpoint)
        return super().run(endpoint, request, file, response_class)
