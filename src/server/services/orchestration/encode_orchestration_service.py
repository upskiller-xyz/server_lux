from typing import Dict, Any
import logging

from src.server.services.remote.contracts import MergerRequest
from src.server.services.remote.contracts.merger_contracts import MergerResponse
from .orchestrator import Orchestrator
from .window_processor import WindowProcessor
from .result_merger import ResultMerger

from ..remote import MergerService
from ...enums import EndpointType, RequestField, ResponseKey
from ..remote.service_map import ServiceEndpointMap
from ...maps import StandardMap
from ...interfaces.orchestration_interfaces import IOrchestrator

logger = logging.getLogger("logger")


class SimulationOrchestrator(IOrchestrator):
    """Orchestrates simulation requests with parallel window processing"""

    def __init__(self):
        self._base_orchestrator = Orchestrator()
        self._window_processor = WindowProcessor(self._base_orchestrator)
        self._merger_service = MergerService

    def run(self, endpoint: EndpointType, request_data: dict, file: Any) -> Dict[str, Any]:
        """Execute simulation with parallel window processing

        Args:
            endpoint: Endpoint type
            request_data: Request parameters including windows
            file: File data if any

        Returns:
            Merged simulation results (with optional window_results if debug_mode=true)
        """
        try:
            window_results = self._window_processor.process_all_windows(endpoint, request_data, file)
        except ValueError as e:
            return {
                ResponseKey.STATUS.value: ResponseKey.ERROR.value,
                ResponseKey.ERROR.value: str(e)
            }

        merged_data = self._merge_window_results(request_data, window_results)

        merger_result = self._call_merger_service(merged_data, file)

        # Check if debug mode is enabled in request
        debug_mode = request_data.get('debug_mode', False)

        return self._build_final_response(merger_result, window_results, debug_mode)

    def _merge_window_results(self, request_data: dict, window_results: list) -> Dict[str, Any]:
        """Merge results from all window processing"""
        merger = ResultMerger(request_data)
        return merger.merge_window_results(window_results)

    def _call_merger_service(self, merged_data: Dict[str, Any], file: Any) -> 'MergerResponse':
        """Call merger service with merged window data"""
        merger_requests = MergerRequest.parse(merged_data)
        merger_request = merger_requests[0] if merger_requests else None

        if not merger_request:
            logger.error("Failed to create MergerRequest")
            raise ValueError("Failed to create merger request")

        merger_endpoint = ServiceEndpointMap.get(self._merger_service)
        return self._merger_service.run(merger_endpoint, merger_request, file)

    def _build_final_response(
        self,
        merger_result: 'MergerResponse',
        window_results: list = None,
        debug_mode: bool = False
    ) -> Dict[str, Any]:
        """Build final response from merger result

        Args:
            merger_result: Merged result from merger service
            window_results: Individual window results (optional, for debug)
            debug_mode: If True, include window_results in response

        Returns:
            Response dict with merged result and optionally individual window results
        """

        response = {
            ResponseKey.STATUS.value: ResponseKey.SUCCESS.value,
            RequestField.RESULT.value: merger_result.result.tolist() if merger_result.result is not None else [],
            RequestField.MASK.value: merger_result.mask.tolist() if merger_result.mask is not None else []
        }

        # Include individual window results only if debug mode is enabled
        if debug_mode and window_results:
            # Convert window results to serializable format
            debug_window_results = {}
            for window_name, result_dict in window_results:
                if isinstance(result_dict, dict):
                    debug_window_results[window_name] = {
                        'result': result_dict.get(RequestField.RESULT.value, []),
                        'mask': result_dict.get(RequestField.MASK.value, [])
                    }
            response['window_results'] = debug_window_results

        return response


class EncodeOrchestrator(IOrchestrator):
    """Orchestrates encode requests using the base orchestrator"""

    def __init__(self):
        self._orchestrator = Orchestrator()

    def run(self, endpoint: EndpointType, request_data: dict, file: Any) -> bytes:
        """Execute encode pipeline and return binary NPZ data

        Args:
            endpoint: Endpoint type
            request_data: Request parameters
            file: File data if any

        Returns:
            Binary NPZ data from encoder service
        """
        result = self._orchestrator.run(endpoint, request_data, file)

        # For encode endpoints, return the binary image data directly
        if RequestField.IMAGE.value in result:
            return result[RequestField.IMAGE.value]

        # No image data found - this is an error
        raise ValueError(f"Encoder service did not return image data. Available keys: {list(result.keys())}")


class EndpointOrchestratorMap(StandardMap):
    _content: Dict[EndpointType, type] = {
        EndpointType.RUN: SimulationOrchestrator,
        EndpointType.SIMULATE: SimulationOrchestrator,
        EndpointType.ENCODE: EncodeOrchestrator,
    }
    _default: type = Orchestrator
