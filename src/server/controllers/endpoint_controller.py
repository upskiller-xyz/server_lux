from typing import Dict, Any
from ..interfaces import ILogger
from ..services.remote_service import ColorManageService, DaylightService, DFEvalService
from ..services.orchestration import OrchestrationService


class EndpointController:
    """Controller for handling endpoint requests"""

    def __init__(
        self,
        colormanage_service: ColorManageService,
        daylight_service: DaylightService,
        df_eval_service: DFEvalService,
        orchestration_service: OrchestrationService,
        logger: ILogger
    ):
        self._colormanage = colormanage_service
        self._daylight = daylight_service
        self._df_eval = df_eval_service
        self._orchestration = orchestration_service
        self._logger = logger

    def to_rgb(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle to_rgb endpoint"""
        self._logger.info("Processing to_rgb request")
        data = request_data.get("data")
        colorscale = request_data.get("colorscale", "df")

        if not data:
            return {"status": "error", "error": "Missing required field: data"}

        return self._colormanage.to_rgb(data, colorscale)

    def to_values(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle to_values endpoint"""
        self._logger.info("Processing to_values request")
        data = request_data.get("data")
        colorscale = request_data.get("colorscale", "df")

        if not data:
            return {"status": "error", "error": "Missing required field: data"}

        return self._colormanage.to_values(data, colorscale)

    def get_df(self, file: Any, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_df endpoint with file upload"""
        self._logger.info("Processing get_df request with file upload")
        return self._daylight.get_df(file, form_data)

    def get_stats(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_stats endpoint"""
        self._logger.info("Processing get_stats request")
        return self._df_eval.get_stats(**request_data)

    def get_df_rgb(self, file: Any, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_df_rgb endpoint (orchestrates get_df + to_rgb) with file upload"""
        self._logger.info("Processing get_df_rgb request with file upload")
        return self._orchestration.get_df_rgb(file, form_data)
