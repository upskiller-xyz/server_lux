from typing import Any, Dict
import logging

from src.server.config import SessionConfig
from src.server.services.http_client import HTTPClient
# from src.server.services.remote.service_map import ServiceResponseMap
from .contracts import RemoteServiceRequest
from .contracts import RemoteServiceResponse, MergerResponse, EncoderResponse, ObstructionResponse, ModelResponse, StatsResponse
from ...enums import ServiceName, EndpointType
from ...maps import  PortMap, StandardMap


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
        """Get request class for endpoint

        Override in subclasses if service supports multiple endpoints
        with different request types.
        """
        return RemoteServiceRequest

    @classmethod
    def _get_url(cls, endpoint: EndpointType) -> str:
        """Get full URL for endpoint"""
        port = PortMap.get(cls.name)
        return f"{SessionConfig.get_url()}:{port.value}/{endpoint.value}"

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

        request_dict = request.to_dict

        response_dict = cls._http_client.post(url, request_dict)

        # Use provided response_class or fall back to service's default
        if response_class is None:
            response_class = ServiceResponseMap.get(cls.__class__)

        response = response_class(response_dict)
        return response.parse()

    @classmethod
    def run_binary(
        cls,
        endpoint: EndpointType,
        request: RemoteServiceRequest,
        response_class: type[RemoteServiceResponse],
        file:Any=None
    ) -> bytes:
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
        response = response_class(binary_data)
        return response.parse()


class ServiceResponseMap(StandardMap):
    _content:Dict[ServiceName, type[RemoteServiceResponse]] = {
        ServiceName.MERGER : MergerResponse,
        ServiceName.ENCODER: EncoderResponse,
        ServiceName.OBSTRUCTION: ObstructionResponse,
        ServiceName.MODEL: ModelResponse,
        ServiceName.STATS: StatsResponse
        
    }
    _default:type[RemoteServiceResponse] = RemoteServiceResponse