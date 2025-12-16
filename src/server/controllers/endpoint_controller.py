from typing import Dict, Any
import time
import math
import base64
import numpy as np
import logging

from src.server.controllers.field_map import FieldMap
# from src.server.maps import EndpointServiceMap
logger = logging.getLogger("logger")
from PIL import Image
from io import BytesIO
from ..interfaces import ILogger
from ..services.remote_service import ObstructionService, EncoderService, ModelService, MergerService, StatsService
from ..services.orchestration import RunOrchestrationService, EncodeOrchestrationService
from ..services.obstruction_calculation import ObstructionCalculationService
from ..enums import EndpointType, RequestField, ResponseKey, ResponseStatus, ImageSize


class FieldValidator:
    """Validates request fields using Strategy pattern"""

    # Common field sets for different endpoint types
    OBSTRUCTION_FIELDS = [
        RequestField.X,
        RequestField.Y,
        RequestField.Z,
        RequestField.DIRECTION_ANGLE,
        RequestField.MESH
    ]

    OBSTRUCTION_MULTI_FIELDS = [
        RequestField.X,
        RequestField.Y,
        RequestField.Z,
        RequestField.DIRECTION_ANGLE,
        RequestField.MESH
    ]

    @staticmethod
    def validate_required_fields(
        request_data: Dict[str, Any],
        required_fields: list[RequestField]
    ) -> Dict[str, Any] | None:
        """Validate that all required fields are present

        Args:
            request_data: Request data dictionary
            required_fields: List of RequestField enums

        Returns:
            Error response dict if validation fails, None if success
        """
        for field in required_fields:
            if field.value not in request_data:
                return {
                    ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                    ResponseKey.ERROR.value: f"Missing required field: {field.value}"
                }
        return None



class ImageResizer:
    """Handles image resizing using Strategy pattern

    Different interpolation methods for different image types:
    - BILINEAR for predictions (smooth gradients)
    - NEAREST for masks (preserve binary values)
    """

    @staticmethod
    def resize_to_target(
        array: np.ndarray,
        interpolation_method: int,
        target_width: int = ImageSize.TARGET_WIDTH.value,
        target_height: int = ImageSize.TARGET_HEIGHT.value
    ) -> np.ndarray:
        """Resize array to target size using specified interpolation

        Args:
            array: Input numpy array
            interpolation_method: PIL interpolation method (Image.BILINEAR or Image.NEAREST)
            target_width: Target width in pixels
            target_height: Target height in pixels

        Returns:
            Resized numpy array normalized to [0, 1]
        """
        target_size = (target_width, target_height)

        if array.shape == target_size:
            return array

        # Convert to PIL image (scale to 0-255)
        img = Image.fromarray((array * 255).astype(np.uint8))

        # Resize with specified interpolation
        img_resized = img.resize(target_size, interpolation_method)

        # Convert back to numpy array and normalize to [0, 1]
        return np.array(img_resized).astype(np.float32) / 255.0


class EndpointController:
    """Controller for handling endpoint requests"""

    # def get_stats(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Handle get_stats endpoint"""
    #     self._logger.info("Processing get_stats request")
    #     return self._df_eval.run(**request_data)

    # def horizon_angle(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Handle horizon_angle endpoint"""
    #     self._logger.info("Processing horizon_angle request")

    #     # Validate required fields using FieldValidator
    #     error = FieldValidator.validate_required_fields(request_data, FieldValidator.OBSTRUCTION_FIELDS)
    #     if error:
    #         return error

    #     # Validate mesh data
    #     mesh = request_data.get(RequestField.MESH.value)
    #     if not isinstance(mesh, list) or len(mesh) < 3:
    #         return {
    #             ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
    #             ResponseKey.ERROR.value: "Mesh must contain at least 3 points"
    #         }

    #     params = FieldValidator.extract_obstruction_params(request_data, mesh)
    #     return self._obstruction.calculate_horizon_angle(**params)

    # def zenith_angle(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Handle zenith_angle endpoint"""
    #     logger.info("Processing zenith_angle request")

    #     # Validate required fields
    #     required_fields = ["x", "y", "z", "rad_x", "rad_y", "mesh"]
    #     for field in required_fields:
    #         if field not in request_data:
    #             return {"status": "error", "error": f"Missing required field: {field}"}

    #     # Validate mesh data
    #     mesh = request_data.get("mesh")
    #     if not isinstance(mesh, list) or len(mesh) < 3:
    #         return {"status": "error", "error": "Mesh must contain at least 3 points"}

    #     return self._obstruction.calculate_zenith_angle(
    #         x=request_data["x"],
    #         y=request_data["y"],
    #         z=request_data["z"],
    #         rad_x=request_data["rad_x"],
    #         rad_y=request_data["rad_y"],
    #         mesh=mesh
    #     )

    # def obstruction(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Handle obstruction endpoint (calculates both horizon and zenith angles)"""
    #     self._logger.info("Processing obstruction request")

    #     # Validate required fields
    #     required_fields = ["x", "y", "z", "rad_x", "rad_y", "mesh"]
    #     for field in required_fields:
    #         if field not in request_data:
    #             return {"status": "error", "error": f"Missing required field: {field}"}

    #     # Validate mesh data
    #     mesh = request_data.get("mesh")
    #     if not isinstance(mesh, list) or len(mesh) < 3:
    #         return {"status": "error", "error": "Mesh must contain at least 3 points"}

    #     return self._obstruction.calculate_obstruction(
    #         x=request_data["x"],
    #         y=request_data["y"],
    #         z=request_data["z"],
    #         rad_x=request_data["rad_x"],
    #         rad_y=request_data["rad_y"],
    #         mesh=mesh
    #     )

    # def obstruction_parallel(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Handle obstruction_parallel endpoint (calculates obstruction for all directions using parallel service)

    #     This endpoint wraps the obstruction_calculation service to provide the same interface
    #     as the remote obstruction service's /obstruction_all endpoint, but using server-side parallelization.

    #     Expected input (two formats supported):
    #         Format 1 (from /run workflow):
    #             x, y, z: Window center coordinates
    #             rad_x, rad_y: Window radii
    #             mesh: 3D geometry mesh

    #         Format 2 (direct call):
    #             x, y, z: Window center coordinates
    #             direction_angle: Window facing direction in radians
    #             mesh: 3D geometry mesh

    #     Returns:
    #         {
    #             "status": "success",
    #             "horizon_angles": [64 floats],
    #             "zenith_angles": [64 floats]
    #         }
    #     """
    #     start_time = time.time()

    #     # Validate mesh data
    #     mesh = request_data.get("mesh", [])
    #     if not isinstance(mesh, list) or len(mesh) < 3:
    #         return {"status": "error", "error": "Mesh must contain at least 3 points"}

    #     # Validate basic coordinates
    #     if "x" not in request_data or "y" not in request_data or "z" not in request_data:
    #         return {"status": "error", "error": "Missing required fields: x, y, z"}

    #     num_mesh_points = len(mesh)
    #     self._logger.info(f"Processing obstruction_parallel request with {num_mesh_points} mesh points")

    #     # Determine direction_angle
    #     if "direction_angle" in request_data:
    #         # Format 2: direction_angle provided directly
    #         direction_angle = request_data["direction_angle"]
    #         self._logger.info(f"Using provided direction_angle: {math.degrees(direction_angle):.2f}°")
    #     elif "rad_x" in request_data and "rad_y" in request_data:
    #         # Format 1: calculate from rad_x, rad_y
    #         direction_angle = math.atan2(request_data["rad_y"], request_data["rad_x"])
    #         self._logger.info(f"Calculated direction_angle from rad_x={request_data['rad_x']}, rad_y={request_data['rad_y']}: {math.degrees(direction_angle):.2f}°")
    #     else:
    #         return {"status": "error", "error": "Missing required field: either 'direction_angle' or both 'rad_x' and 'rad_y'"}

    #     # Call the parallel obstruction calculation service
    #     result = self._obstruction_calculation.calculate_multi_direction(
    #         x=request_data["x"],
    #         y=request_data["y"],
    #         z=request_data["z"],
    #         direction_angle=direction_angle,
    #         mesh=mesh,
    #         start_angle=17.5,
    #         end_angle=162.5,
    #         num_directions=64
    #     )

    #     elapsed_time = time.time() - start_time
    #     self._logger.info(f"obstruction_parallel request completed in {elapsed_time:.2f}s")

    #     # Transform result to match expected format
    #     if result.get("status") == "success":
    #         data = result.get("data", {})
    #         return {
    #             "status": "success",
    #             "horizon_angles": data.get("horizon_angles", []),
    #             "zenith_angles": data.get("zenith_angles", [])
    #         }
    #     else:
    #         return result

    # def obstruction_multi(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Handle obstruction_multi endpoint (calculates obstruction for 64 directions)

    #     The start_angle and end_angle parameters use a half-circle coordinate system where:
    #     - 0° = 90° counter-clockwise from the window normal (left edge)
    #     - 90° = the window normal (direction_angle parameter)
    #     - 180° = 90° clockwise from the window normal (right edge)

    #     Default values (17.5° to 162.5°) skip the extreme edges of the half-circle.
    #     """
    #     start_time = time.time()

    #     mesh = request_data.get("mesh", [])
    #     num_mesh_points = len(mesh)
    #     self._logger.info(f"Processing obstruction_multi request with {num_mesh_points} mesh points")

    #     # Validate required fields
    #     required_fields = ["x", "y", "z", "direction_angle", "mesh"]
    #     for field in required_fields:
    #         if field not in request_data:
    #             return {"status": "error", "error": f"Missing required field: {field}"}

    #     # Validate mesh data
    #     if not isinstance(mesh, list) or len(mesh) < 3:
    #         return {"status": "error", "error": "Mesh must contain at least 3 points"}

    #     # Get optional parameters (in half-circle coordinate system where 90° = direction_angle)
    #     start_angle = request_data.get("start_angle", 17.5)
    #     end_angle = request_data.get("end_angle", 162.5)
    #     num_directions = request_data.get("num_directions", 64)

    #     result = self._obstruction_calculation.calculate_multi_direction(
    #         x=request_data["x"],
    #         y=request_data["y"],
    #         z=request_data["z"],
    #         direction_angle=request_data["direction_angle"],
    #         mesh=mesh,
    #         start_angle=start_angle,
    #         end_angle=end_angle,
    #         num_directions=num_directions
    #     )

    #     elapsed_time = time.time() - start_time
    #     self._logger.info(f"obstruction_multi request completed in {elapsed_time:.2f}s")

    #     return result

    # def encode_raw(self, request_data: Dict[str, Any]) -> bytes:
    #     """Handle encode_raw endpoint (direct call to remote encode service without obstruction calculation)

    #     This endpoint only validates parameters and directly calls the remote /encode service.
    #     No obstruction calculation is performed.
    #     """
    #     self._logger.info("Processing encode_raw request")

    #     # Validate required fields
    #     required_fields = ["model_type", "parameters"]
    #     for field in required_fields:
    #         if field not in request_data:
    #             raise ValueError(f"Missing required field: {field}")

    #     # Validate parameters structure
    #     parameters = request_data.get("parameters")
    #     if not isinstance(parameters, dict):
    #         raise ValueError("Parameters must be a dictionary")

    #     return self._encoder.encode(
    #         model_type=request_data["model_type"],
    #         parameters=parameters
    #     )

    # def encode(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Handle encode endpoint (obstruction calculation → encoding, no simulation)

    #     Similar to /run but without daylight simulation and postprocessing.
    #     Calculates obstruction angles and encodes the room data for each window.
    #     """
    #     logger.info("Processing encode request")

    #     # Validate required fields
    #     required_fields = ["model_type", "parameters", "mesh"]
    #     for field in required_fields:
    #         if field not in request_data:
    #             return {"status": "error", "error": f"Missing required field: {field}"}

    #     # Validate parameters structure
    #     parameters = request_data.get("parameters")
    #     if not isinstance(parameters, dict):
    #         return {"status": "error", "error": "Parameters must be a dictionary"}

    #     # Validate windows in parameters
    #     if "windows" not in parameters:
    #         return {"status": "error", "error": "Missing required field: parameters.windows"}

    #     # Validate mesh data
    #     mesh = request_data.get("mesh")
    #     if not isinstance(mesh, list) or len(mesh) < 3:
    #         return {"status": "error", "error": "Mesh must contain at least 3 points"}

    #     return self._encode_orchestration.encode_with_obstruction(request_data)

    @classmethod
    def _validate(cls, request_data, fields):
        for field in fields:
            if field.value not in request_data:
                return field
        parameters = request_data.get(RequestField.PARAMETERS.value)
        if not isinstance(parameters, dict):
            return RequestField.PARAMETERS

        # Validate mesh data
        mesh = request_data.get(RequestField.MESH)
        if not isinstance(mesh, list):
            return RequestField.MESH
        return ""
    @classmethod
    def run(cls, endpoint:EndpointType, request_data: Dict[str, Any], file:Any=None) -> Dict[str, Any]:
        """Handle run endpoint (complete simulation: obstruction → encoding → daylight)"""
        logger.info("Processing {} request".format(endpoint.value))
        
        
        orchestrator = EndpointOrchestratorMap.get(endpoint)
        required_fields = FieldMap.get(endpoint)
        missing_field = cls._validate(request_data, required_fields)
        if missing_field:
            return {"status": "error", "error": f"Missing required field: {missing_field}"}

        # Validate parameters structure
        
        return orchestrator.run(endpoint, request_data, file)

        return self._run_orchestration.run_simulation(request_data)

    # def get_df_direct(self, file: Any = None, request_data: Dict[str, Any] = None) -> Dict[str, Any]:
    #     """Handle get_df endpoint with direct image input (file upload or base64)

    #     Sends image directly to simulation service for prediction.
    #     Supports both file upload and base64-encoded image data.

    #     Args:
    #         file: Uploaded file object (multipart/form-data)
    #         request_data: JSON data containing either:
    #             - image_base64: base64-encoded image string
    #             - image_array: nested list representing numpy array
    #             - invert_channels: optional bool (default: True)

    #     Returns:
    #         Simulation result from model service
    #     """
    #     self._logger.info("Processing get_df_direct request")

    #     invert_channels = False
    #     if request_data:
    #         invert_channels = request_data.get("invert_channels", False)

    #     try:
    #         # Case 1: File upload
    #         if file is not None:
    #             self._logger.info(f"Processing file upload: {file.filename}")
    #             image_bytes = file.stream.read()
    #             return self._model.run(image_bytes, invert_channels=invert_channels)

    #         # Case 2: Base64-encoded image
    #         if request_data and "image_base64" in request_data:
    #             self._logger.info("Processing base64-encoded image")
    #             image_base64 = request_data["image_base64"]
    #             image_bytes = base64.b64decode(image_base64)
    #             return self._model.run(image_bytes, invert_channels=invert_channels)

    #         # Case 3: Numpy array (as nested list)
    #         if request_data and "image_array" in request_data:
    #             self._logger.info("Processing numpy array")
    #             image_array = np.array(request_data["image_array"])
    #             return self._model.run(image_array, invert_channels=invert_channels)

    #         # No valid input provided
    #         return {
    #             "status": "error",
    #             "error": "No image data provided. Expected either file upload, image_base64, or image_array"
    #         }

    #     except ValueError as e:
    #         self._logger.error(f"Invalid input format: {str(e)}")
    #         return {"status": "error", "error": str(e)}
    #     except Exception as e:
    #         self._logger.error(f"Failed to process image: {str(e)}")
    #         return {"status": "error", "error": f"Failed to process image: {str(e)}"}

    # def merge(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Handle merge endpoint (merge multiple window simulations into room result)

    #     Expected request_data format:
    #     {
    #         "room_polygon": [[x, y], ...],
    #         "windows": {
    #             "window_name": {
    #                 "x1": float, "y1": float, "z1": float,
    #                 "x2": float, "y2": float, "z2": float,
    #                 "direction_angle": float
    #             }
    #         },
    #         "simulations": {
    #             "window_name": {
    #                 "df_values": [[float]],
    #                 "mask": [[int]]
    #             }
    #         }
    #     }

    #     Returns:
    #     {
    #         "status": "success" | "error",
    #         "df_matrix": [[float]],
    #         "room_mask": [[int]]
    #     }
    #     """
    #     self._logger.info("Processing merge request")

    #     # Validate required fields
    #     required_fields = ["room_polygon", "windows", "simulations"]
    #     for field in required_fields:
    #         if field not in request_data:
    #             return {"status": "error", "error": f"Missing required field: {field}"}

    #     # Validate room_polygon
    #     room_polygon = request_data.get("room_polygon")
    #     if not isinstance(room_polygon, list) or len(room_polygon) < 3:
    #         return {"status": "error", "error": "room_polygon must contain at least 3 points"}

    #     # Validate windows
    #     windows = request_data.get("windows")
    #     if not isinstance(windows, dict):
    #         return {"status": "error", "error": "windows must be a dictionary"}

    #     # Validate simulations
    #     simulations = request_data.get("simulations")
    #     if not isinstance(simulations, dict):
    #         return {"status": "error", "error": "simulations must be a dictionary"}

    #     # Call merger service
    #     return self._merger.run(
    #         room_polygon=room_polygon,
    #         windows=windows,
    #         simulations=simulations
    #     )

    # def stats(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
    #     """Handle stats endpoint (calculate statistics on daylight factor data)

    #     Expected request_data format:
    #     {
    #         "df_values": [[float]],  # 2D array of daylight factor values
    #         "mask": [[int]]           # 2D binary mask indicating valid areas
    #     }

    #     Returns:
    #         Statistics calculation result from stats service
    #     """
    #     self._logger.info("Processing stats request")

    #     # Validate required fields
    #     required_fields = ["df_values", "mask"]
    #     for field in required_fields:
    #         if field not in request_data:
    #             return {"status": "error", "error": f"Missing required field: {field}"}

    #     # Validate df_values
    #     df_values = request_data.get("df_values")
    #     if not isinstance(df_values, list):
    #         return {"status": "error", "error": "df_values must be a list"}

    #     # Validate mask
    #     mask = request_data.get("mask")
    #     if not isinstance(mask, list):
    #         return {"status": "error", "error": "mask must be a list"}

    #     # Call stats service
    #     return self._stats.run(
    #         df_values=df_values,
    #         mask=mask
    #     )
