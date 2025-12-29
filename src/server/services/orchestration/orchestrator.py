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
        service_endpoint = ServiceEndpointMap.get(service)

        executor = ExecutorFactory.create(len(requests))
        return executor.execute(service, service_endpoint, requests, file)

    def _parse_requests(self, service: type, endpoint: EndpointType,
                       params: Dict[str, Any]) -> list:
        """Parse request parameters into service request objects"""
        request_class = service._get_request(endpoint)

        if hasattr(request_class, 'parse'):
            requests = request_class.parse(params)
        else:
            requests = [request_class(**params)]

        return requests if isinstance(requests, list) else [requests]

    def _update_params(self, params: Dict[str, Any], response: Any) -> None:
        """Update parameters with service response"""
        if isinstance(response, dict):
            params.update(response)
        elif isinstance(response, bytes):
            self._handle_binary_response(params, response)

    def _handle_binary_response(self, params: Dict[str, Any], response: bytes) -> None:
        """Handle binary response (e.g., NPZ from encoder)"""
        masks = self._mask_extractor.extract_from_npz(response, params)
        if masks:
            params[RequestField.MASK.value] = masks

        params[RequestField.IMAGE.value] = response
