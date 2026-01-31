from typing import Any, Dict
import logging

from .service_executor import ExecutorFactory
from .mask_extractor import MaskExtractor
from ..remote.service_map import EndpointServiceMap, ServiceEndpointMap
from ...enums import EndpointType, RequestField, ResponseKey
from ...interfaces.orchestration_interfaces import IOrchestrator

logger = logging.getLogger("logger")


class Orchestrator(IOrchestrator):
    """Orchestrates sequential service calls through a pipeline"""

    def __init__(self):
        self._mask_extractor = MaskExtractor()

    def run(self, endpoint: EndpointType, request_data: dict, file: Any) -> Dict[str, Any]:
        """Execute service pipeline for an endpoint

        Args:
            endpoint: The endpoint type to process
            request_data: Request parameters
            file: File data if any

        Returns:
            Merged response from all services
        """
        services = EndpointServiceMap.get(endpoint)
        params = request_data.copy()
        response = {}

        for service in services:
            # Skip service if its output already exists in params
            if self._should_skip_service(service, params):
                logger.debug(f"Skipping {service.__name__} - output already exists in params")
                continue

            response = self._execute_service(service, endpoint, params, file)
            self._update_params(params, response)

        if ResponseKey.STATUS.value not in params:
            params[ResponseKey.STATUS.value] = ResponseKey.SUCCESS.value

        # Remove mask and result from final response for stats endpoint
        if endpoint == EndpointType.STATS_CALCULATE:
            params.pop(RequestField.MASK.value, None)
            params.pop(RequestField.RESULT.value, None)

        return params

    def _execute_service(self, service: type, endpoint: EndpointType,
                        params: Dict[str, Any], file: Any) -> Any:
        """Execute a single service in the pipeline"""
        requests = self._parse_requests(service, endpoint, params)

        # Use the original endpoint for single-endpoint services like obstruction
        # Otherwise use the mapped service endpoint
        service_endpoint = self._get_service_endpoint(service, endpoint)

        executor = ExecutorFactory.create(len(requests))
        return executor.execute(service, service_endpoint, requests, file)

    def _get_service_endpoint(self, service: type, endpoint: EndpointType) -> EndpointType:
        """Get the endpoint to call for a service

        For ObstructionService, use the original endpoint (zenith, horizon, etc.)
        For other services, use the mapped endpoint
        """
        from ..remote import ObstructionService

        # For obstruction endpoints, use the original endpoint
        if service == ObstructionService and endpoint in [
            EndpointType.ZENITH, EndpointType.HORIZON,
            EndpointType.OBSTRUCTION, EndpointType.OBSTRUCTION_ALL,
            EndpointType.OBSTRUCTION_MULTI, EndpointType.OBSTRUCTION_PARALLEL
        ]:
            return endpoint

        # For other services, use the mapped endpoint
        return ServiceEndpointMap.get(service)

    def _parse_requests(self, service: type, endpoint: EndpointType,
                       params: Dict[str, Any]) -> list:
        """Parse request parameters into service request objects"""
        request_class = service._get_request(endpoint)

        if hasattr(request_class, 'parse'):
            requests = request_class.parse(params)
        else:
            requests = [request_class(**params)]

        return requests if isinstance(requests, list) else [requests]

    def _should_skip_service(self, service: type, params: Dict[str, Any]) -> bool:
        """Determine if a service should be skipped based on existing data

        Args:
            service: The service class to check
            params: Current request parameters

        Returns:
            True if service should be skipped, False otherwise
        """
        from ..remote import ObstructionService

        # Skip ObstructionService if both horizon and zenith already exist
        if service == ObstructionService:
            has_horizon = ResponseKey.HORIZON.value in params
            has_zenith = ResponseKey.ZENITH.value in params
            return has_horizon and has_zenith

        return False

    def _update_params(self, params: Dict[str, Any], response: Any) -> None:
        """Update parameters with service response"""
        if isinstance(response, dict):
            params.update(response)
        elif isinstance(response, bytes):
            self._handle_binary_response(params, response)
        elif hasattr(response, 'to_dict'):
            # Handle response objects (dataclasses with to_dict property)
            params.update(response.to_dict)

    def _handle_binary_response(self, params: Dict[str, Any], response: bytes) -> None:
        """Handle binary response (e.g., NPZ from encoder)"""
        masks = self._mask_extractor.extract_from_npz(response, params)
        if masks:
            params[RequestField.MASK.value] = masks

        params[RequestField.IMAGE.value] = response
