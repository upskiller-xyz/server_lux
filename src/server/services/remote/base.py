import logging
from typing import TYPE_CHECKING, Any, Dict

from src.server.config import get_service_config
from src.server.services.helpers.logging_utils import LoggingFormatter
from src.server.services.http_client import HTTPClient

from ...constants import ServiceUrlBuilder
from ...enums import EndpointType, ServiceName
from ...maps import StandardMap
from .contracts import (
    BinaryResponse,
    EncoderResponse,
    MergerResponse,
    ModelResponse,
    ObstructionResponse,
    RemoteServiceRequest,
    RemoteServiceResponse,
    StatsResponse,
)
from .outbound_auth import BackendAuthMap, BackendResolver

if TYPE_CHECKING:
    pass

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
        # Genuinely circular: service_map imports RemoteService from this
        # module, so this one stays function-local by design.
        from .service_map import ServiceRequestMap  # noqa: PLC0415
        return ServiceRequestMap.get(cls.name)

    @classmethod
    def _get_url(cls, endpoint: EndpointType) -> str:
        """Get full URL for endpoint"""
        config = get_service_config()
        base_url = config.get_service_url(cls.name.value)
        return ServiceUrlBuilder.endpoint(base_url, endpoint.value)

    @classmethod
    def _log_request(cls, endpoint: EndpointType, url: str, request: RemoteServiceRequest | None = None) -> None:
        """Log request being made"""
        logger.info("Calling %s service: %s", cls.name.value, url)

    @classmethod
    def _auth_headers(cls, url: str) -> Dict[str, str]:
        """Resolve outbound auth headers for a service call.

        The hosting backend is selected from the URL: Modal-hosted endpoints
        (``*.modal.run``) get proxy-auth headers, private Scaleway serverless
        endpoints (``*.scw.cloud``) get an ``X-Auth-Token``, plain container
        endpoints get none. The service (``cls.name``) is passed on too, since a
        backend may resolve per-service credentials (Scaleway reads a per-service
        token env var); the URL selects the backend, the service selects the token.
        """
        backend = BackendResolver.resolve(url)
        return BackendAuthMap.get(backend).headers(cls.name)


    @classmethod
    def run(
        cls,
        endpoint: EndpointType,
        request: RemoteServiceRequest,
        file:Any=None,
        response_class: type[RemoteServiceResponse] | None = None
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

        logger.info("[%s] Calling remote endpoint: %s", cls.name.value, url)

        request_dict = request.to_dict
        formatted_request = LoggingFormatter.format_for_logging(request_dict)
        logger.debug("[%s] Request data: %s", cls.name.value, formatted_request)

        response_dict = cls._http_client.post(url, request_dict, headers=cls._auth_headers(url))

        formatted_response = LoggingFormatter.format_for_logging(response_dict)
        logger.debug("[%s] Response received: %s", cls.name.value, formatted_response)


        if response_class is None:
            response_class = ServiceResponseMap.get(cls.name)
            
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

        # Convert request to dict
        request_dict = request.to_dict

        binary_data = cls._http_client.post_binary(url, request_dict, headers=cls._auth_headers(url))
        
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