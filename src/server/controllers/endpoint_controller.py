from typing import Dict, Any
import time
import numpy as np
from PIL import Image
from io import BytesIO
from ..interfaces import ILogger
from ..services.remote_service import ColorManageService, DaylightService, DFEvalService, ObstructionService, EncoderService, ModelService, MergerService
from ..services.orchestration import OrchestrationService, RunOrchestrationService, EncodeOrchestrationService
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
        encode_orchestration_service: EncodeOrchestrationService,
        model_service: 'ModelService',
        merger_service: 'MergerService',
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
        self._encode_orchestration = encode_orchestration_service
        self._model = model_service
        self._merger = merger_service
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

    def obstruction_parallel(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle obstruction_parallel endpoint (calculates obstruction for all directions using parallel service)

        This endpoint wraps the obstruction_calculation service to provide the same interface
        as the remote obstruction service's /obstruction_all endpoint, but using server-side parallelization.

        Expected input (two formats supported):
            Format 1 (from /run workflow):
                x, y, z: Window center coordinates
                rad_x, rad_y: Window radii
                mesh: 3D geometry mesh

            Format 2 (direct call):
                x, y, z: Window center coordinates
                direction_angle: Window facing direction in radians
                mesh: 3D geometry mesh

        Returns:
            {
                "status": "success",
                "horizon_angles": [64 floats],
                "zenith_angles": [64 floats]
            }
        """
        start_time = time.time()

        # Validate mesh data
        mesh = request_data.get("mesh", [])
        if not isinstance(mesh, list) or len(mesh) < 3:
            return {"status": "error", "error": "Mesh must contain at least 3 points"}

        # Validate basic coordinates
        if "x" not in request_data or "y" not in request_data or "z" not in request_data:
            return {"status": "error", "error": "Missing required fields: x, y, z"}

        num_mesh_points = len(mesh)
        self._logger.info(f"Processing obstruction_parallel request with {num_mesh_points} mesh points")

        # Determine direction_angle
        import math
        if "direction_angle" in request_data:
            # Format 2: direction_angle provided directly
            direction_angle = request_data["direction_angle"]
            self._logger.info(f"Using provided direction_angle: {math.degrees(direction_angle):.2f}°")
        elif "rad_x" in request_data and "rad_y" in request_data:
            # Format 1: calculate from rad_x, rad_y
            direction_angle = math.atan2(request_data["rad_y"], request_data["rad_x"])
            self._logger.info(f"Calculated direction_angle from rad_x={request_data['rad_x']}, rad_y={request_data['rad_y']}: {math.degrees(direction_angle):.2f}°")
        else:
            return {"status": "error", "error": "Missing required field: either 'direction_angle' or both 'rad_x' and 'rad_y'"}

        # Call the parallel obstruction calculation service
        result = self._obstruction_calculation.calculate_multi_direction(
            x=request_data["x"],
            y=request_data["y"],
            z=request_data["z"],
            direction_angle=direction_angle,
            mesh=mesh,
            start_angle=17.5,
            end_angle=162.5,
            num_directions=64
        )

        elapsed_time = time.time() - start_time
        self._logger.info(f"obstruction_parallel request completed in {elapsed_time:.2f}s")

        # Transform result to match expected format
        if result.get("status") == "success":
            data = result.get("data", {})
            return {
                "status": "success",
                "horizon_angles": data.get("horizon_angles", []),
                "zenith_angles": data.get("zenith_angles", [])
            }
        else:
            return result

    def obstruction_multi(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle obstruction_multi endpoint (calculates obstruction for 64 directions)

        The start_angle and end_angle parameters use a half-circle coordinate system where:
        - 0° = 90° counter-clockwise from the window normal (left edge)
        - 90° = the window normal (direction_angle parameter)
        - 180° = 90° clockwise from the window normal (right edge)

        Default values (17.5° to 162.5°) skip the extreme edges of the half-circle.
        """
        start_time = time.time()

        mesh = request_data.get("mesh", [])
        num_mesh_points = len(mesh)
        self._logger.info(f"Processing obstruction_multi request with {num_mesh_points} mesh points")

        # Validate required fields
        required_fields = ["x", "y", "z", "direction_angle", "mesh"]
        for field in required_fields:
            if field not in request_data:
                return {"status": "error", "error": f"Missing required field: {field}"}

        # Validate mesh data
        if not isinstance(mesh, list) or len(mesh) < 3:
            return {"status": "error", "error": "Mesh must contain at least 3 points"}

        # Get optional parameters (in half-circle coordinate system where 90° = direction_angle)
        start_angle = request_data.get("start_angle", 17.5)
        end_angle = request_data.get("end_angle", 162.5)
        num_directions = request_data.get("num_directions", 64)

        result = self._obstruction_calculation.calculate_multi_direction(
            x=request_data["x"],
            y=request_data["y"],
            z=request_data["z"],
            direction_angle=request_data["direction_angle"],
            mesh=mesh,
            start_angle=start_angle,
            end_angle=end_angle,
            num_directions=num_directions
        )

        elapsed_time = time.time() - start_time
        self._logger.info(f"obstruction_multi request completed in {elapsed_time:.2f}s")

        return result

    def encode_raw(self, request_data: Dict[str, Any]) -> bytes:
        """Handle encode_raw endpoint (direct call to remote encode service without obstruction calculation)

        This endpoint only validates parameters and directly calls the remote /encode service.
        No obstruction calculation is performed.
        """
        self._logger.info("Processing encode_raw request")

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

    def encode(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle encode endpoint (obstruction calculation → encoding, no simulation)

        Similar to /run but without daylight simulation and postprocessing.
        Calculates obstruction angles and encodes the room data for each window.
        """
        self._logger.info("Processing encode request")

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

        return self._encode_orchestration.encode_with_obstruction(request_data)

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

    def get_df_direct(self, file: Any = None, request_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handle get_df endpoint with direct image input (file upload or base64)

        Sends image directly to simulation service for prediction.
        Supports both file upload and base64-encoded image data.

        Args:
            file: Uploaded file object (multipart/form-data)
            request_data: JSON data containing either:
                - image_base64: base64-encoded image string
                - image_array: nested list representing numpy array
                - invert_channels: optional bool (default: True)

        Returns:
            Simulation result from model service
        """
        self._logger.info("Processing get_df_direct request")

        invert_channels = False
        if request_data:
            invert_channels = request_data.get("invert_channels", False)

        try:
            # Case 1: File upload
            if file is not None:
                self._logger.info(f"Processing file upload: {file.filename}")
                image_bytes = file.stream.read()
                return self._model.get_df(image_bytes, invert_channels=invert_channels)

            # Case 2: Base64-encoded image
            if request_data and "image_base64" in request_data:
                self._logger.info("Processing base64-encoded image")
                import base64
                image_base64 = request_data["image_base64"]
                image_bytes = base64.b64decode(image_base64)
                return self._model.get_df(image_bytes, invert_channels=invert_channels)

            # Case 3: Numpy array (as nested list)
            if request_data and "image_array" in request_data:
                self._logger.info("Processing numpy array")
                image_array = np.array(request_data["image_array"])
                return self._model.get_df(image_array, invert_channels=invert_channels)

            # No valid input provided
            return {
                "status": "error",
                "error": "No image data provided. Expected either file upload, image_base64, or image_array"
            }

        except ValueError as e:
            self._logger.error(f"Invalid input format: {str(e)}")
            return {"status": "error", "error": str(e)}
        except Exception as e:
            self._logger.error(f"Failed to process image: {str(e)}")
            return {"status": "error", "error": f"Failed to process image: {str(e)}"}

    def merge(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle merge endpoint (merge multiple window simulations into room result)

        Expected request_data format:
        {
            "room_polygon": [[x, y], ...],
            "windows": {
                "window_name": {
                    "x1": float, "y1": float, "z1": float,
                    "x2": float, "y2": float, "z2": float,
                    "direction_angle": float
                }
            },
            "simulations": {
                "window_name": {
                    "df_values": [[float]],
                    "mask": [[int]]
                }
            }
        }

        Returns:
        {
            "status": "success" | "error",
            "df_matrix": [[float]],
            "room_mask": [[int]]
        }
        """
        self._logger.info("Processing merge request")

        # Validate required fields
        required_fields = ["room_polygon", "windows", "simulations"]
        for field in required_fields:
            if field not in request_data:
                return {"status": "error", "error": f"Missing required field: {field}"}

        # Validate room_polygon
        room_polygon = request_data.get("room_polygon")
        if not isinstance(room_polygon, list) or len(room_polygon) < 3:
            return {"status": "error", "error": "room_polygon must contain at least 3 points"}

        # Validate windows
        windows = request_data.get("windows")
        if not isinstance(windows, dict):
            return {"status": "error", "error": "windows must be a dictionary"}

        # Validate simulations
        simulations = request_data.get("simulations")
        if not isinstance(simulations, dict):
            return {"status": "error", "error": "simulations must be a dictionary"}

        # Call merger service
        return self._merger.merge(
            room_polygon=room_polygon,
            windows=windows,
            simulations=simulations
        )
