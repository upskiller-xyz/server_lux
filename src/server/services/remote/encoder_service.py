from typing import Any

from .contracts import RemoteServiceRequest, MainRequest
from .contracts import BinaryResponse
from ...enums import ServiceName, EndpointType
from .base import RemoteService


class EncoderService(RemoteService):
    """Service for encoding room data to images

    Handles /encode endpoint only.
    Follows Single Responsibility Principle - only handles image encoding.
    """
    name: ServiceName = ServiceName.ENCODER

    @classmethod
    def _get_request(cls, endpoint: EndpointType) -> type[RemoteServiceRequest]:
        """Get request class for endpoint"""
        return MainRequest

    @classmethod
    def _get_response(cls, endpoint: EndpointType) -> type[BinaryResponse]:
        """Get response class for endpoint"""
        return BinaryResponse

    @classmethod
    def run(cls, endpoint: EndpointType, request: RemoteServiceRequest, file: Any = None) -> bytes:
        """Encode room parameters to image"""
        response_class = cls._get_response(endpoint)
        return super().run_binary(endpoint, request, response_class)
