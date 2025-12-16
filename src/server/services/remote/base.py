from typing import Any
import logging

from src.server.config import SessionConfig
from src.server.services.http_client import HTTPClient
from src.server.services.remote.service_map import ServiceResponseMap
from ...interfaces.remote_interfaces import RemoteServiceRequest, RemoteServiceResponse
from ...enums import ServiceName, EndpointType
from ...maps import  PortMap


logger = logging.getLogger('logger')


class RemoteService:
    """Base class for all remote service implementations

    Static class - no instantiation required.
    All parameters passed as inputs to run methods.
    """
    name: ServiceName = ServiceName.ENCODER

    @classmethod
    def _get_url(cls, endpoint: EndpointType) -> str:
        """Get full URL for endpoint"""
        port = PortMap.get(cls.name)
        return f"{SessionConfig.get_url()}:{port.value}/{endpoint.value}"

    @classmethod
    def _log_request(cls, endpoint: EndpointType, url: str) -> None:
        """Log request being made"""
        logger.info(f"Calling {cls.name.value} service: {url}")
        

    @classmethod
    def run(
        cls,
        endpoint: EndpointType,
        request: RemoteServiceRequest,
        file:Any=None
    ) -> Any:
        """Template method for standard request/response flow

        Args:
            endpoint: Endpoint to call
            request: Typed request object
            response_class: Response class to parse with
            http_client: HTTP client instance
            base_url: Base URL for service

        Returns:
            Parsed response data
        """
        url = cls._get_url(endpoint)
        cls._log_request(endpoint, url)
        response_dict = HTTPClient.post(url, request.to_dict)
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
        binary_data = HTTPClient.post_binary(url, request.to_dict)
        response = response_class(binary_data)
        return response.parse()
