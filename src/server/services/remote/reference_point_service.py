from typing import Any, Dict

from ...enums import EndpointType, ServiceName
from .base import RemoteService
from .contracts import (
    ReferencePointRequest,
    ReferencePointResponse,
    RemoteServiceRequest,
)


class ReferencePointService(RemoteService):
    """Service for calculating window reference points

    Handles /get-reference-point endpoint.
    Follows Single Responsibility Principle - only calculates reference points.
    """
    name: ServiceName = ServiceName.ENCODER  # Uses encoder microservice

    @classmethod
    def _get_request(cls, endpoint: EndpointType) -> type[RemoteServiceRequest]:
        """Get request class for endpoint"""
        return ReferencePointRequest

    @classmethod
    def _get_response(cls, endpoint: EndpointType) -> type[ReferencePointResponse]:
        """Get response class for endpoint"""
        return ReferencePointResponse

    @classmethod
    def run(cls, endpoint: EndpointType, request: RemoteServiceRequest, file: Any = None) -> Dict[str, Any]:
        """Calculate reference points for windows"""
        response_class = cls._get_response(endpoint)
        return super().run(endpoint, request, file, response_class)
