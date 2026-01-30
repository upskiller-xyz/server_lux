from typing import Any, Dict, TYPE_CHECKING
import logging

from src.server.config import SessionConfig, get_service_config
from src.server.services.http_client import HTTPClient
from src.server.services.helpers.logging_utils import LoggingFormatter
from .contracts import RemoteServiceRequest
from .contracts import RemoteServiceResponse, MergerResponse, EncoderResponse, ObstructionResponse, ModelResponse, StatsResponse, BinaryResponse
from ...enums import ServiceName, EndpointType
from ...maps import  PortMap, StandardMap

if TYPE_CHECKING:
    from .service_map import ServiceRequestMap

logger = logging.getLogger('logger')





class RemoteService:
    """Base class for all remote service implementations

    Static class - no instantiation required.
    All parameters passed as inputs to run methods.
    """
    name: ServiceName = ServiceName.ENCODER
    _http_client: HTTPClient = HTTPClient()

    @classmethod
    def _get_request(cls, endpoint: EndpointType) -> type[RemoteServiceRequest]:
        """Get request class for endpoint using ServiceRequestMap

        Uses Strategy Pattern - maps service name to request class.
        """
        from .service_map import ServiceRequestMap
        return ServiceRequestMap.get(cls.name)

    @classmethod
    def _get_url(cls, endpoint: EndpointType) -> str:
        """Get full URL for endpoint"""
        config = get_service_config()
        base_url = config.get_service_url(cls.name.value)
        return f"{base_url}/{endpoint.value}"

    @classmethod
    def _log_request(cls, endpoint: EndpointType, url: str, request: RemoteServiceRequest = None) -> None:
        """Log request being made"""
        logger.info(f"Calling {cls.name.value} service: {url}")


    @classmethod
    def run(
        cls,
        endpoint: EndpointType,
        request: RemoteServiceRequest,
        file:Any=None,
        response_class: type[RemoteServiceResponse] = None
    ) -> Any:
        """Template method for standard request/response flow

        Args:
            endpoint: Endpoint to call
            request: Typed request object
            file: Optional file upload
            response_class: Response class to parse with (optional, defaults to service's response class)

        Returns:
            Parsed response data
        """
        url = cls._get_url(endpoint)
        cls._log_request(endpoint, url, request)

        logger.info(f"[{cls.name.value}] Calling remote endpoint: {url}")

        request_dict = request.to_dict
        formatted_request = LoggingFormatter.format_for_logging(request_dict)
        logger.info(f"[{cls.name.value}] Request data: {formatted_request}")

        response_dict = cls._http_client.post(url, request_dict)

        formatted_response = LoggingFormatter.format_for_logging(response_dict)
        logger.info(f"[{cls.name.value}] Response received: {formatted_response}")

        # Use provided response_class or fall back to service's default
        if response_class is None:
            response_class = ServiceResponseMap.get(cls.name)

        # Factory Pattern: All response classes use classmethod parse(content) -> Object
        return response_class.parse(response_dict)

    @classmethod
    def run_binary(
        cls,
        endpoint: EndpointType,
        request: RemoteServiceRequest,
        response_class: type[BinaryResponse],
        file:Any=None
    ) -> BinaryResponse:
        """Template method for binary response flow

        Args:
            endpoint: Endpoint to call
            request: Typed request object
            response_class: Binary response class
            http_client: HTTP client instance
            base_url: Base URL for service

        Returns:
            Binary data
        """
        url = cls._get_url(endpoint)
        cls._log_request(endpoint, url)

        # Convert request to dict and log it
        request_dict = request.to_dict

        binary_data = cls._http_client.post_binary(url, request_dict)
        
        # Factory Pattern: Check for explicit marker
        
        return response_class(binary_data)


class ServiceResponseMap(StandardMap):
    _content:Dict[ServiceName, type[RemoteServiceResponse]] = {
        ServiceName.MERGER : MergerResponse,
        ServiceName.ENCODER: EncoderResponse,
        ServiceName.OBSTRUCTION: ObstructionResponse,
        ServiceName.MODEL: ModelResponse,
        ServiceName.STATS: StatsResponse
        
    }
    _default:type[RemoteServiceResponse] = RemoteServiceResponse