from typing import Dict, Any
import io

from src.server.interfaces.remote_interfaces import RemoteServiceRequest, RemoteServiceResponse
from src.server.services.http_client import HTTPClient
from ...enums import ServiceName, EndpointType, RequestField
from .base import RemoteService
from .image_converters import ImageChannelInverter
import logging

logger = logging.getLogger('logger')


class ModelService(RemoteService):
    """Service for running model inference"""
    name: ServiceName = ServiceName.MODEL

    @classmethod
    def run(
        cls,
        endpoint: EndpointType,
        request: RemoteServiceRequest,
        response_class: type[RemoteServiceResponse], file:Any=None
    ) -> Any:
        """Template method for standard request/response flow

        Args:
            endpoint: Endpoint to call
            request: Typed request object
            response_class: Response class to parse with
            http_client: HTTP client instance
            base_url: Base URL for service

            image_bytes: Image data as bytes
            http_client: HTTP client instance
            base_url: Base URL for service
            filename: Name of the image file (default: "image.png")
            invert_channels: If True, convert RGB to BGR before sending (default: False)

        Returns:
            Parsed response data
        """
        
        url = cls._get_url(endpoint)
        cls._log_request(endpoint, url)

        channel_inverter = ImageChannelInverter()
        image_bytes = channel_inverter.invert(request.image_bytes, request.invert_channels)

        # Prepare file for multipart upload
        files = {RequestField.FILE.value: (request.filename, io.BytesIO(image_bytes), "image/png")}

        response_dict = HTTPClient.post_multipart(url, files, {})
        # response_dict = HTTPClient.post(url, request.to_dict)
        response = response_class(response_dict)
        return response.parse()
    