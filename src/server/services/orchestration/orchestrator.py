from typing import Any, Dict
import logging

from .service_executor import ExecutorFactory
from .mask_extractor import MaskExtractor
from ..remote.service_map import EndpointServiceMap, ServiceEndpointMap
from ..remote import DirectionAngleService
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
        """Execute a single service in the pipeline
        
        Handles special case for DirectionAngleService where windows may already
        have pre-calculated direction_angle values.
        """
        # Special handling for DirectionAngleService to preserve pre-calculated angles
        pre_calculated_angles = {}
        if service == DirectionAngleService:
            pre_calculated_angles = self._extract_pre_calculated_angles(params)
        
        requests = self._parse_requests(service, endpoint, params)

        # Use the original endpoint for single-endpoint services like obstruction
        # Otherwise use the mapped service endpoint
        service_endpoint = self._get_service_endpoint(service, endpoint)

        executor = ExecutorFactory.create(len(requests))
        response = executor.execute(service, service_endpoint, requests, file)
        
        # Merge pre-calculated angles back into response for DirectionAngleService
        if service == DirectionAngleService and pre_calculated_angles:
            # Convert response object to dict if needed
            response_dict = response
            if hasattr(response, 'to_dict'):
                response_dict = response.to_dict
            
            if isinstance(response_dict, dict) and ResponseKey.DIRECTION_ANGLE.value in response_dict:
                # Merge pre-calculated angles with computed ones
                response_dict[ResponseKey.DIRECTION_ANGLE.value].update(pre_calculated_angles)
                response = response_dict
        
        return response

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

    def _extract_pre_calculated_angles(self, params: Dict[str, Any]) -> Dict[str, float]:
        """Extract pre-calculated direction_angle values from window data
        
        Uses Enumerator Pattern - all string keys use RequestField/ResponseKey enums.
        
        Args:
            params: Request parameters containing windows
            
        Returns:
            Dictionary mapping window names to pre-calculated direction angles
        """
        pre_calculated = {}
        
        # Handle both direct windows or windows nested in parameters
        windows_data = params.get(RequestField.WINDOWS.value)
        if not windows_data:
            # Check if windows are nested in parameters
            params_section = params.get(RequestField.PARAMETERS.value, {})
            windows_data = params_section.get(RequestField.WINDOWS.value, {})
        
        if isinstance(windows_data, dict):
            for window_name, window_config in windows_data.items():
                # Check if this window has pre-calculated direction_angle using enum
                if isinstance(window_config, dict):
                    direction_angle = window_config.get(RequestField.DIRECTION_ANGLE.value)
                    if direction_angle is not None:
                        pre_calculated[window_name] = direction_angle
                        
        return pre_calculated

    def _update_params(self, params: Dict[str, Any], response: Any) -> None:
        """Update parameters with service response
        
        Handles special conversion of top-level direction_angle to direction_angle dict
        when reference_point has been calculated.
        Uses Enumerator Pattern - all string keys use RequestField/ResponseKey enums.
        """
        if isinstance(response, dict):
            params.update(response)
            
            # Special handling: if we have a top-level direction_angle and reference_point,
            # convert the top-level value to a dict mapping window names to that value
            # This handles the case where a single window has a pre-calculated direction_angle
            # and we need it in the format expected by ObstructionRequest.parse()
            if (RequestField.DIRECTION_ANGLE.value in params and 
                RequestField.REFERENCE_POINT.value in params):
                
                direction_angle_value = params.get(RequestField.DIRECTION_ANGLE.value)
                reference_points = params.get(RequestField.REFERENCE_POINT.value, {})
                
                # If direction_angle is NOT already a dict, convert it to one
                # mapping each window name to the single direction_angle value
                if not isinstance(direction_angle_value, dict) and reference_points:
                    direction_angles_dict = {}
                    for window_name in reference_points.keys():
                        direction_angles_dict[window_name] = direction_angle_value
                    params[RequestField.DIRECTION_ANGLE.value] = direction_angles_dict
                    
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
