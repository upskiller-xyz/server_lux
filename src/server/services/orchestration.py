from typing import Dict, Any, List
import concurrent.futures
from ..interfaces import ILogger
from .remote_service import ColorManageService, DaylightService, ObstructionService, EncoderService


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


class RunOrchestrationService:
    """Service for orchestrating the complete run workflow:
    obstruction angles → encoding → daylight simulation"""

    def __init__(
        self,
        obstruction_service: ObstructionService,
        encoder_service: EncoderService,
        daylight_service: DaylightService,
        logger: ILogger
    ):
        self._obstruction = obstruction_service
        self._encoder = encoder_service
        self._daylight = daylight_service
        self._logger = logger

    def _process_single_window(
        self,
        window_name: str,
        window_data: Dict[str, Any],
        model_type: str,
        parameters: Dict[str, Any],
        mesh: List,
        translation: Dict[str, float],
        rotation: List[float]
    ) -> Dict[str, Any]:
        """Process a single window: obstruction → encoding → simulation

        Args:
            window_name: Name/identifier of the window
            window_data: Window parameters
            model_type: Model type for encoding
            parameters: Room parameters
            mesh: Obstruction mesh
            translation: Translation parameters
            rotation: Rotation parameters

        Returns:
            Result dictionary with window_name and simulation result or error
        """
        from io import BytesIO

        self._logger.info(f"Processing window: {window_name}")

        try:
            # Step 1: Calculate window center position
            x = (window_data.get("x1", 0) + window_data.get("x2", 0)) / 2
            y = (window_data.get("y1", 0) + window_data.get("y2", 0)) / 2
            z = (window_data.get("z1", 0) + window_data.get("z2", 0)) / 2
            rad_x = window_data.get("rad_x", 0.5)
            rad_y = window_data.get("rad_y", 0.5)

            # Step 2: Calculate obstruction angles for this window
            self._logger.info(f"[{window_name}] Calculating obstruction angles at ({x}, {y}, {z})")
            obstruction_result = self._obstruction.calculate_obstruction_all(
                x=x, y=y, z=z,
                rad_x=rad_x, rad_y=rad_y,
                mesh=mesh
            )

            if obstruction_result.get("status") == "error":
                self._logger.error(f"[{window_name}] Obstruction calculation failed")
                return {
                    "window_name": window_name,
                    "status": "error",
                    "error": f"Obstruction calculation failed: {obstruction_result.get('error')}"
                }

            horizon_angles = obstruction_result.get("horizon_angles", [])
            zenith_angles = obstruction_result.get("zenith_angles", [])

            if len(horizon_angles) != 64 or len(zenith_angles) != 64:
                error_msg = f"Expected 64 angles each, got horizon: {len(horizon_angles)}, zenith: {len(zenith_angles)}"
                self._logger.error(f"[{window_name}] {error_msg}")
                return {
                    "window_name": window_name,
                    "status": "error",
                    "error": error_msg
                }

            # Step 3: Create parameters with single window enhanced with obstruction angles
            single_window_params = parameters.copy()
            single_window_params["windows"] = {
                window_name: {
                    **window_data,
                    "obstruction_angle_horizon": horizon_angles,
                    "obstruction_angle_zenith": zenith_angles
                }
            }

            # Step 4: Encode with obstruction angles
            self._logger.info(f"[{window_name}] Encoding room with obstruction angles")
            encoded_image_bytes = self._encoder.encode(
                model_type=model_type,
                parameters=single_window_params
            )

            # Step 5: Run daylight simulation on encoded image
            self._logger.info(f"[{window_name}] Running daylight simulation")

            # Create mock file object
            class MockFile:
                def __init__(self, content, filename, content_type):
                    self.stream = BytesIO(content)
                    self.filename = filename
                    self.content_type = content_type

            mock_file = MockFile(encoded_image_bytes, f"encoded_{window_name}.png", "image/png")
            form_data = {
                "translation": str(translation),
                "rotation": str(rotation)
            }

            daylight_result = self._daylight.get_df(mock_file, form_data)

            if daylight_result.get("status") == "error":
                self._logger.error(f"[{window_name}] Daylight simulation failed")
                return {
                    "window_name": window_name,
                    "status": "error",
                    "error": f"Daylight simulation failed: {daylight_result.get('error')}"
                }

            self._logger.info(f"[{window_name}] Processing completed successfully")
            return {
                "window_name": window_name,
                "status": "success",
                "result": daylight_result
            }

        except Exception as e:
            self._logger.error(f"[{window_name}] Processing failed: {str(e)}")
            return {
                "window_name": window_name,
                "status": "error",
                "error": str(e)
            }

    def run_simulation(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute complete simulation workflow for each window

        Args:
            request_data: Contains model_type, parameters with windows, and mesh

        Returns:
            Dictionary with results for each window
        """
        self._logger.info("Starting run_simulation orchestration")

        # Step 1: Extract parameters
        model_type = request_data.get("model_type")
        parameters = request_data.get("parameters", {})
        windows = parameters.get("windows", {})
        mesh = request_data.get("mesh")

        # Use default values for translation and rotation (will be integrated later)
        translation = {"x": 0, "y": 0}
        rotation = [0]

        # Validate required fields
        if not model_type:
            return {"status": "error", "error": "Missing required field: model_type"}
        if not parameters:
            return {"status": "error", "error": "Missing required field: parameters"}
        if not windows:
            return {"status": "error", "error": "Missing required field: parameters.windows"}
        if not isinstance(windows, dict):
            return {"status": "error", "error": "Windows must be a dictionary"}
        if not mesh:
            return {"status": "error", "error": "Missing required field: mesh"}
        if not isinstance(mesh, list) or len(mesh) < 3:
            return {"status": "error", "error": "Mesh must contain at least 3 points"}

        # Validate each window
        required_window_fields = ["x1", "y1", "z1", "x2", "y2", "z2",
                                  "window_sill_height", "window_frame_ratio", "window_height"]
        for window_name, window_data in windows.items():
            for field in required_window_fields:
                if field not in window_data:
                    return {"status": "error", "error": f"Window '{window_name}' missing required field: {field}"}

        # Process each window through complete workflow
        results = {}
        for window_name, window_data in windows.items():
            result = self._process_single_window(
                window_name=window_name,
                window_data=window_data,
                model_type=model_type,
                parameters=parameters,
                mesh=mesh,
                translation=translation,
                rotation=rotation
            )
            results[window_name] = result

        # Return results for all windows
        return {
            "status": "success",
            "results": results
        }
