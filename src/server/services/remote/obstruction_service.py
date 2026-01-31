from typing import Dict, Any, List, cast
import asyncio
import time
import math
import logging

from src.server.services.helpers.parallel import ParallelRequest
from src.server.services.remote.contracts.obstruction_contracts import ObstructionResponse
logger = logging.getLogger("logger")
from .contracts import ObstructionRequest, RemoteServiceRequest, RemoteServiceResponse
# from .contracts import ObstructionResponse
from ...enums import ServiceName, EndpointType, RequestField, ResponseKey, ResponseStatus
from .base import RemoteService
from ...services.obstruction.calculator_interface import IObstructionCalculator


class ObstructionService(RemoteService):
    """Service for obstruction angle calculations"""
    name: ServiceName = ServiceName.OBSTRUCTION

    @classmethod
    def _get_request(cls, endpoint: EndpointType) -> type[RemoteServiceRequest]:
        """Get request class for endpoint

        All obstruction endpoints use ObstructionRequest
        """
        return ObstructionRequest

    @classmethod
    def run(cls, endpoint: EndpointType, request: RemoteServiceRequest, file: Any = None, response_class: type[RemoteServiceResponse] = ObstructionResponse) -> Dict[str, Any]:
        """Calculate obstruction angles and format response for orchestration"""
        # response is now an ObstructionResponse object
        response = super().run(endpoint, request, file, response_class)

        logger.info(f"[ObstructionService] Raw response from remote: {response}")

        # Cast to ObstructionRequest since _get_request returns ObstructionRequest
        obstruction_request = cast(ObstructionRequest, request)
        window_name = obstruction_request.window_name

        # Access attributes directly from the dataclass/object
        horizon_angles = response.horizon_angle if response.horizon_angle is not None else []
        zenith_angles = response.zenith_angle if response.zenith_angle is not None else []

        logger.info(f"[ObstructionService] Parsed horizon_angles: {horizon_angles}")
        logger.info(f"[ObstructionService] Parsed zenith_angles: {zenith_angles}")

        # For single-window requests (default window name), return flat structure
        # For multi-window orchestration, return nested structure
        horizon_params = horizon_angles
        zenith_params = zenith_angles
        if window_name != "window":
            horizon_params = {window_name: horizon_angles}
            zenith_params = {window_name: zenith_angles}
        return {
            ResponseKey.HORIZON.value: horizon_params,
            ResponseKey.ZENITH.value: zenith_params
        }
    

