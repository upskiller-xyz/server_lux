from typing import Any
import io
import logging

from .contracts import RemoteServiceRequest, ModelRequest, RemoteServiceResponse
from .base import RemoteService, ServiceResponseMap
from .image_converters import EncoderOutputConverter
from ...enums import ServiceName, EndpointType, RequestField

logger = logging.getLogger('logger')


class ModelService(RemoteService):
    """Service for running model inference"""
    name: ServiceName = ServiceName.MODEL

    @classmethod
    def _get_request(cls, endpoint: EndpointType) -> type[RemoteServiceRequest]:
        """Get request class for endpoint"""
        return ModelRequest

    @classmethod
    def run(
        cls,
        endpoint: EndpointType,
        request: ModelRequest,
        file: Any = None,
        response_class: type[RemoteServiceResponse] | None = None
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

        # Convert encoder output (ZIP/NPY) to PNG
        converter = EncoderOutputConverter()
        image_bytes = converter.convert_to_png(request.image)

        # Prepare file for multipart upload
        files = {RequestField.FILE.value: (request.filename, io.BytesIO(image_bytes), "image/png")}

        response_dict = cls._http_client.post_multipart(url, files, {})

        # Use provided response_class or fall back to service's default
        if response_class is None:
            response_class = ServiceResponseMap.get(cls.name)
            
        return response_class.parse(response_dict)
    