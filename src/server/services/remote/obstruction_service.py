from typing import Dict, Any, List
import asyncio
import time
import math
import logging

from src.server.services.helpers.parallel import ParallelRequest
logger = logging.getLogger("logger")
from .contracts import ObstructionRequest, RemoteServiceRequest
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
    def run(cls, endpoint: EndpointType, request: RemoteServiceRequest, file: Any = None, response_class: type = None) -> Dict[str, Any]:
        """Calculate obstruction angles and format response for orchestration"""
        # response is now an ObstructionResponse object
        response = super().run(endpoint, request, file, response_class)

        window_name = request.window_name

        # Access attributes directly from the dataclass/object
        horizon_angles = response.horizon_angle if response.horizon_angle is not None else []
        zenith_angles = response.zenith_angle if response.zenith_angle is not None else []

        return {
            RequestField.OBSTRUCTION_ANGLE_HORIZON.value: {window_name: horizon_angles},
            RequestField.OBSTRUCTION_ANGLE_ZENITH.value: {window_name: zenith_angles}
        }
    

