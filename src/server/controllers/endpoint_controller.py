from typing import Dict, Any
from ..interfaces import ILogger
from ..services.remote_service import ColorManageService, DaylightService, DFEvalService, ObstructionService, EncoderService
from ..services.orchestration import OrchestrationService, RunOrchestrationService
from ..services.obstruction_calculation import ObstructionCalculationService


class EndpointController:
    """Controller for handling endpoint requests"""

    def __init__(
        self,
        colormanage_service: ColorManageService,
        daylight_service: DaylightService,
        df_eval_service: DFEvalService,
        obstruction_service: ObstructionService,
        obstruction_calculation_service: ObstructionCalculationService,
        encoder_service: EncoderService,
        orchestration_service: OrchestrationService,
        run_orchestration_service: RunOrchestrationService,
        logger: ILogger
    ):
        self._colormanage = colormanage_service
        self._daylight = daylight_service
        self._df_eval = df_eval_service
        self._obstruction = obstruction_service
        self._obstruction_calculation = obstruction_calculation_service
        self._encoder = encoder_service
        self._orchestration = orchestration_service
        self._run_orchestration = run_orchestration_service
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
        """Handle get_df endpoint with file upload (legacy)"""
        self._logger.info("Processing get_df request with file upload")
        return self._daylight.get_df(file, form_data)

    def simulate(self, file: Any, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle simulate endpoint with file upload"""
        self._logger.info("Processing simulate request with file upload")
        return self._daylight.simulate(file, form_data)

    def get_stats(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_stats endpoint"""
        self._logger.info("Processing get_stats request")
        return self._df_eval.get_stats(**request_data)

    def get_df_rgb(self, file: Any, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_df_rgb endpoint (orchestrates get_df + to_rgb) with file upload"""
        self._logger.info("Processing get_df_rgb request with file upload")
        return self._orchestration.get_df_rgb(file, form_data)

    def horizon_angle(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle horizon_angle endpoint"""
        self._logger.info("Processing horizon_angle request")

        # Validate required fields
        required_fields = ["x", "y", "z", "rad_x", "rad_y", "mesh"]
        for field in required_fields:
            if field not in request_data:
                return {"status": "error", "error": f"Missing required field: {field}"}

        # Validate mesh data
        mesh = request_data.get("mesh")
        if not isinstance(mesh, list) or len(mesh) < 3:
            return {"status": "error", "error": "Mesh must contain at least 3 points"}

        return self._obstruction.calculate_horizon_angle(
            x=request_data["x"],
            y=request_data["y"],
            z=request_data["z"],
            rad_x=request_data["rad_x"],
            rad_y=request_data["rad_y"],
            mesh=mesh
        )

    def zenith_angle(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle zenith_angle endpoint"""
        self._logger.info("Processing zenith_angle request")

        # Validate required fields
        required_fields = ["x", "y", "z", "rad_x", "rad_y", "mesh"]
        for field in required_fields:
            if field not in request_data:
                return {"status": "error", "error": f"Missing required field: {field}"}

        # Validate mesh data
        mesh = request_data.get("mesh")
        if not isinstance(mesh, list) or len(mesh) < 3:
            return {"status": "error", "error": "Mesh must contain at least 3 points"}

        return self._obstruction.calculate_zenith_angle(
            x=request_data["x"],
            y=request_data["y"],
            z=request_data["z"],
            rad_x=request_data["rad_x"],
            rad_y=request_data["rad_y"],
            mesh=mesh
        )

    def obstruction(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle obstruction endpoint (calculates both horizon and zenith angles)"""
        self._logger.info("Processing obstruction request")

        # Validate required fields
        required_fields = ["x", "y", "z", "rad_x", "rad_y", "mesh"]
        for field in required_fields:
            if field not in request_data:
                return {"status": "error", "error": f"Missing required field: {field}"}

        # Validate mesh data
        mesh = request_data.get("mesh")
        if not isinstance(mesh, list) or len(mesh) < 3:
            return {"status": "error", "error": "Mesh must contain at least 3 points"}

        return self._obstruction.calculate_obstruction(
            x=request_data["x"],
            y=request_data["y"],
            z=request_data["z"],
            rad_x=request_data["rad_x"],
            rad_y=request_data["rad_y"],
            mesh=mesh
        )

    def obstruction_multi(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle obstruction_multi endpoint (calculates obstruction for 64 directions)"""
        self._logger.info("Processing obstruction_multi request")

        # Validate required fields
        required_fields = ["x", "y", "z", "direction_angle", "mesh"]
        for field in required_fields:
            if field not in request_data:
                return {"status": "error", "error": f"Missing required field: {field}"}

        # Validate mesh data
        mesh = request_data.get("mesh")
        if not isinstance(mesh, list) or len(mesh) < 3:
            return {"status": "error", "error": "Mesh must contain at least 3 points"}

        # Get optional parameters
        start_angle = request_data.get("start_angle", 17.5)
        end_angle = request_data.get("end_angle", 162.5)
        num_directions = request_data.get("num_directions", 64)

        return self._obstruction_calculation.calculate_multi_direction(
            x=request_data["x"],
            y=request_data["y"],
            z=request_data["z"],
            direction_angle=request_data["direction_angle"],
            mesh=mesh,
            start_angle=start_angle,
            end_angle=end_angle,
            num_directions=num_directions
        )

    def encode(self, request_data: Dict[str, Any]) -> bytes:
        """Handle encode endpoint (encodes room data to PNG image)"""
        self._logger.info("Processing encode request")

        # Validate required fields
        required_fields = ["model_type", "parameters"]
        for field in required_fields:
            if field not in request_data:
                raise ValueError(f"Missing required field: {field}")

        # Validate parameters structure
        parameters = request_data.get("parameters")
        if not isinstance(parameters, dict):
            raise ValueError("Parameters must be a dictionary")

        return self._encoder.encode(
            model_type=request_data["model_type"],
            parameters=parameters
        )

    def run(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle run endpoint (complete simulation: obstruction → encoding → daylight)"""
        self._logger.info("Processing run request")

        # Validate required fields
        required_fields = ["model_type", "parameters", "mesh"]
        for field in required_fields:
            if field not in request_data:
                return {"status": "error", "error": f"Missing required field: {field}"}

        # Validate parameters structure
        parameters = request_data.get("parameters")
        if not isinstance(parameters, dict):
            return {"status": "error", "error": "Parameters must be a dictionary"}

        # Validate windows in parameters
        if "windows" not in parameters:
            return {"status": "error", "error": "Missing required field: parameters.windows"}

        # Validate mesh data
        mesh = request_data.get("mesh")
        if not isinstance(mesh, list) or len(mesh) < 3:
            return {"status": "error", "error": "Mesh must contain at least 3 points"}

        return self._run_orchestration.run_simulation(request_data)
