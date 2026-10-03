import logging
from typing import Any, Dict, Optional

from src.server.controllers.field_map import EndpointOrchestratorMap, FieldMap
from src.server.controllers.validation_strategy import ValidationStrategy

from ..enums import EndpointType
from ..response_builder import ErrorResponseBuilder
from ..services.helpers.timing import StageTimer

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
            Response dictionary

        Raises:
            RequestValidationError: on missing/invalid input fields (mapped to 400)
        """
        logger.info(f"Processing {endpoint.value} request")

        # Validate required fields using Strategy pattern. Missing or malformed
        # input raises instead of returning an error dict: dicts fall through
        # ResponseBuilder's 500 path, exceptions map to the 400 contract.
        required_fields = FieldMap.get(endpoint)
        with StageTimer("validate_fields", logger):
            self._validator.validate_fields(request_data, required_fields)

        # Get and instantiate appropriate orchestrator
        orchestrator_class = EndpointOrchestratorMap.get(endpoint)
        orchestrator = orchestrator_class()

        with StageTimer("orchestrator.run", logger):
            return orchestrator.run(endpoint, request_data, file)
