from typing import Any, Dict

from .contracts import RemoteServiceRequest
from .contracts.external_reference_point_contracts import ExternalReferencePointRequest, ExternalReferencePointResponse
from ...enums import ServiceName, EndpointType
from .base import RemoteService


class ExternalReferencePointService(RemoteService):
    """Service for calculating external window reference points

    Handles /get-external-reference-point endpoint.
    Follows Single Responsibility Principle - only calculates external reference points.
    
    The external reference point is the point on the opposite edge of the window
    from the edge that lies on the room polygon (i.e., the external face of the window).
    
    This is used for obstruction calculations, where we want to measure obstruction
    from the external side of the window, not the interior reference point.
    """
    name: ServiceName = ServiceName.ENCODER  # Uses encoder microservice

    @classmethod
    def _get_request(cls, endpoint: EndpointType) -> type[RemoteServiceRequest]:
        """Get request class for endpoint"""
        return ExternalReferencePointRequest

    @classmethod
    def _get_response(cls, endpoint: EndpointType) -> type:
        """Get response class for endpoint"""
        return ExternalReferencePointResponse

    @classmethod
    def run(cls, endpoint: EndpointType, request: RemoteServiceRequest, file: Any = None) -> Dict[str, Any]:
        """Calculate external reference points for windows"""
        response_class = cls._get_response(endpoint)
        return super().run(endpoint, request, file, response_class)
