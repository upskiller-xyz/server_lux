from typing import Dict, Any
from ..interfaces import ILogger
from .remote_service import ColorManageService, DaylightService


class OrchestrationService:
    """Service for orchestrating multiple remote service calls"""

    def __init__(
        self,
        colormanage_service: ColorManageService,
        daylight_service: DaylightService,
        logger: ILogger
    ):
        self._colormanage = colormanage_service
        self._daylight = daylight_service
        self._logger = logger

    def get_df_rgb(self, file: Any, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get dataframe and convert to RGB (get_df + to_rgb) with file upload"""
        self._logger.info("Orchestrating get_df_rgb operation")

        # Step 1: Get dataframe from daylight service
        df_result = self._daylight.get_df(file, form_data)

        if df_result.get("status") == "error":
            self._logger.error("get_df call failed")
            return df_result

        # Step 2: Convert result to RGB
        # Assuming df_result contains the data to convert
        data_to_convert = df_result.get("data")
        if not data_to_convert:
            self._logger.error("No data received from get_df")
            return {"status": "error", "error": "No data from get_df"}

        colorscale = form_data.get("colorscale", "df")
        rgb_result = self._colormanage.to_rgb(data_to_convert, colorscale)

        return rgb_result
