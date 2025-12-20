from typing import Dict, Any, Optional
import logging

from src.server.controllers.field_map import EndpointOrchestratorMap, FieldMap
from src.server.controllers.validation_strategy import ValidationStrategy
from ..enums import EndpointType
from ..response_builder import ErrorResponseBuilder

logger = logging.getLogger("logger")


class EndpointController:
    """Controller for handling endpoint requests"""

    def __init__(self):
        self._validator = ValidationStrategy()
        self._error_builder = ErrorResponseBuilder()

    def run(self, endpoint: EndpointType, request_data: Dict[str, Any], file: Any = None) -> Dict[str, Any]:
        """Handle endpoint request with validation and orchestration

        Args:
            endpoint: The endpoint type to process
            request_data: Request parameters
            file: File data if any

        Returns:
            Response dictionary or error response
        """
        logger.info(f"Processing {endpoint.value} request")

        # Validate required fields using Strategy pattern
        required_fields = FieldMap.get(endpoint)
        validation_error = self._validator.validate_fields(request_data, required_fields)
        if validation_error:
            return validation_error

        # Get and instantiate appropriate orchestrator
        orchestrator_class = EndpointOrchestratorMap.get(endpoint)
        orchestrator = orchestrator_class()

        return orchestrator.run(endpoint, request_data, file)
