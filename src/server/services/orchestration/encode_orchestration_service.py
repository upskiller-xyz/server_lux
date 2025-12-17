from typing import Dict, Any, List
import time
import base64
import os

from src.server.interfaces.remote_interfaces import MainRequest, MergerRequest
from src.server.services.helpers.parallel import ParallelRequest

from ..remote import MergerService
from ...enums import EndpointType
from ...services.remote.service_map import EndpointServiceMap, ServiceRequestMap

class Orchestrator:

    @classmethod
    def run(cls, endpoint:EndpointType, request_data:dict, file:Any):
        services = EndpointServiceMap.get(endpoint)
        request = ServiceRequestMap.get(services[0])(**request_data, file=file)
        _params = request_data.to_dict()
        response = {}
        for i, service in enumerate(services):
            request = ServiceRequestMap.get(services[i])(**_params, file=file)
            response = service.run(request)
            _params.update(response)
                
        return response
    
class MultiOrchestrator:

    @classmethod
    def run(cls, endpoint:EndpointType, request_data:dict, file:Any):
        
        results = ParallelRequest.run(Orchestrator.run, (endpoint, request_data, file))
        return results
    
class SimulationOrchestrator:

    @classmethod
    def run(cls, endpoint:EndpointType, request_data:dict, file:Any):
        request = MainRequest(request_data)
        results = ParallelRequest.run(Orchestrator.run, (endpoint, request, file))
        request = request.update(results)
        request = MergerRequest(request)
        
        result = MergerService.run(endpoint, request, file)
        return result

# class EncodeOrchestrationService:
#     """Service for orchestrating the encode workflow:
#     obstruction angles → encoding (no simulation, no postprocessing)"""

#     def __init__(
#         self,
#         obstruction_calculation_service: ObstructionCalculationService,
#         encoder_service: EncoderService,
#         logger: ILogger
#     ):
#         self._obstruction_calculation = obstruction_calculation_service
#         self._encoder = encoder_service
#         self._logger = logger
#         self._validator = ParameterValidator()

#     def _is_local_deployment(self) -> bool:
#         """Check if running in local deployment mode"""
#         deployment_mode = os.getenv("DEPLOYMENT_MODE", "local")
#         return deployment_mode == "local"

#     def _process_single_window_encode(
#         self,
#         window_name: str,
#         window_data: Dict[str, Any],
#         model_type: str,
#         parameters: Dict[str, Any],
#         mesh: List
#     ) -> Dict[str, Any]:
#         """Process a single window: obstruction → encoding (no simulation)

#         Args:
#             window_name: Name/identifier of the window
#             window_data: Window parameters
#             model_type: Model type for encoding
#             parameters: Room parameters
#             mesh: Obstruction mesh

#         Returns:
#             Result dictionary with window_name and encoded image bytes or error
#         """
#         self._logger.info(f"[Encode] Processing window: {window_name}")

#         try:
#             # Step 1: Calculate window center position
#             x = (window_data.get(RequestField.X1.value, 0) + window_data.get(RequestField.X2.value, 0)) / 2
#             y = (window_data.get(RequestField.Y1.value, 0) + window_data.get(RequestField.Y2.value, 0)) / 2
#             z = (window_data.get(RequestField.Z1.value, 0) + window_data.get(RequestField.Z2.value, 0)) / 2

#             # Step 2: Calculate obstruction angles for this window
#             obstruction_start = time.time()
#             self._logger.info(f"[{window_name}] Calculating obstruction angles at ({x}, {y}, {z})")

#             # Determine direction_angle using DirectionAngleResolver (Strategy pattern)
#             direction_angle = DirectionAngleResolver.resolve(
#                 window_name, window_data, parameters, self._encoder, self._logger
#             )

#             if direction_angle is None:
#                 return {
#                     ResponseKey.WINDOW_NAME.value: window_name,
#                     ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
#                     ResponseKey.ERROR.value: "Failed to calculate direction_angle"
#                 }

#             # Use parallel obstruction calculation service
#             obstruction_result = self._obstruction_calculation.calculate_multi_direction(
#                 x=x, y=y, z=z,
#                 direction_angle=direction_angle,
#                 mesh=mesh,
#                 start_angle=17.5,
#                 end_angle=162.5,
#                 num_directions=64
#             )

#             obstruction_time = time.time() - obstruction_start
#             self._logger.info(f"[{window_name}] Obstruction calculation completed in {obstruction_time:.2f}s")

#             if obstruction_result.get(ResponseKey.STATUS.value) == ResponseStatus.ERROR.value:
#                 self._logger.error(f"[{window_name}] Obstruction calculation failed")
#                 return {
#                     ResponseKey.WINDOW_NAME.value: window_name,
#                     ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
#                     ResponseKey.ERROR.value: f"Obstruction calculation failed: {obstruction_result.get(ResponseKey.ERROR.value)}"
#                 }

#             # Extract angles from the result data
#             result_data = obstruction_result.get(ResponseKey.DATA.value, {})
#             horizon_angles = result_data.get(ResponseKey.HORIZON_ANGLES.value, [])
#             zenith_angles = result_data.get(ResponseKey.ZENITH_ANGLES.value, [])

#             if len(horizon_angles) != 64 or len(zenith_angles) != 64:
#                 error_msg = f"Expected 64 angles each, got horizon: {len(horizon_angles)}, zenith: {len(zenith_angles)}"
#                 self._logger.error(f"[{window_name}] {error_msg}")
#                 return {
#                     ResponseKey.WINDOW_NAME.value: window_name,
#                     ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
#                     ResponseKey.ERROR.value: error_msg
#                 }

#             # Step 3: Create parameters with single window enhanced with obstruction angles
#             single_window_params = parameters.copy()

#             # Prepare window data for encoder v2.0.1 using RequestField enums
#             # Only send required fields: position (x1,y1,z1,x2,y2,z2), window_frame_ratio, direction_angle, and obstruction angles
#             encoder_window_data = {
#                 RequestField.X1.value: window_data.get(RequestField.X1.value),
#                 RequestField.Y1.value: window_data.get(RequestField.Y1.value),
#                 RequestField.Z1.value: window_data.get(RequestField.Z1.value),
#                 RequestField.X2.value: window_data.get(RequestField.X2.value),
#                 RequestField.Y2.value: window_data.get(RequestField.Y2.value),
#                 RequestField.Z2.value: window_data.get(RequestField.Z2.value),
#                 RequestField.WINDOW_FRAME_RATIO.value: window_data.get(RequestField.WINDOW_FRAME_RATIO.value),
#                 RequestField.DIRECTION_ANGLE.value: direction_angle,
#                 RequestField.OBSTRUCTION_ANGLE_HORIZON.value: horizon_angles,
#                 RequestField.OBSTRUCTION_ANGLE_ZENITH.value: zenith_angles
#             }

#             single_window_params[RequestField.WINDOWS.value] = {
#                 window_name: encoder_window_data
#             }

#             # Step 4: Encode with obstruction angles
#             self._logger.info(f"[{window_name}] Encoding room with obstruction angles (direction_angle={direction_angle:.4f} rad)")

#             encoded_image_bytes = self._encoder.encode(
#                 model_type=model_type,
#                 parameters=single_window_params
#             )

#             self._logger.info(f"[{window_name}] Encoding completed successfully ({len(encoded_image_bytes)} bytes)")

#             # Base64-encode the image so it can be JSON-serialized
#             encoded_image_b64 = base64.b64encode(encoded_image_bytes).decode('utf-8')

#             return {
#                 "window_name": window_name,
#                 "status": "success",
#                 "encoded_image": encoded_image_b64,  # Base64-encoded string
#                 "image_size": len(encoded_image_bytes),
#                 "x1": window_data.get("x1"),
#                 "y1": window_data.get("y1"),
#                 "z1": window_data.get("z1"),
#                 "x2": window_data.get("x2"),
#                 "y2": window_data.get("y2"),
#                 "z2": window_data.get("z2")
#             }

#         except ServiceAuthorizationError as e:
#             self._logger.error(f"[{window_name}] {e.get_log_message()}")
#             return {
#                 "window_name": window_name,
#                 "status": "error",
#                 "error": e.get_user_message(),
#                 "error_type": "authorization_error"
#             }

#         except ServiceConnectionError as e:
#             is_local = self._is_local_deployment()
#             user_message = e.get_user_message(is_local)
#             self._logger.error(f"[{window_name}] {e.get_log_message()}")

#             return {
#                 "window_name": window_name,
#                 "status": "error",
#                 "error": user_message,
#                 "error_type": "connection_error"
#             }

#         except ServiceTimeoutError as e:
#             self._logger.error(f"[{window_name}] {e.get_log_message()}")
#             return {
#                 "window_name": window_name,
#                 "status": "error",
#                 "error": f"Request timeout: {e.service_name} service did not respond within {e.timeout_seconds} seconds",
#                 "error_type": "timeout_error"
#             }

#         except ServiceResponseError as e:
#             self._logger.error(f"[{window_name}] {e.get_log_message()}")
#             return {
#                 "window_name": window_name,
#                 "status": "error",
#                 "error": f"Service error: {e.service_name} returned status {e.status_code} - {e.error_message}",
#                 "error_type": "response_error"
#             }

#         except Exception as e:
#             self._logger.error(f"[{window_name}] Processing failed: {str(e)}")
#             return {
#                 "window_name": window_name,
#                 "status": "error",
#                 "error": str(e)
#             }

#     def encode_with_obstruction(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
#         """Execute encode workflow for each window: obstruction → encoding

#         Args:
#             request_data: Contains model_type, parameters with windows, and mesh

#         Returns:
#             Dictionary with encoded images for each window
#         """
#         self._logger.info("Starting encode_with_obstruction orchestration")

#         # Extract parameters using RequestField enums
#         model_type = request_data.get(RequestField.MODEL_TYPE.value)
#         parameters = request_data.get(RequestField.PARAMETERS.value, {})
#         windows = parameters.get(RequestField.WINDOWS.value, {})
#         mesh = request_data.get(RequestField.MESH.value)

#         # Validate using ParameterValidator
#         validation_result = self._validator.validate_model_type(model_type)
#         if validation_result.get("status") == "error":
#             return validation_result

#         validation_result = self._validator.validate_parameters(parameters)
#         if validation_result.get("status") == "error":
#             return validation_result

#         validation_result = self._validator.validate_windows(windows)
#         if validation_result.get("status") == "error":
#             return validation_result

#         validation_result = self._validator.validate_mesh(mesh)
#         if validation_result.get("status") == "error":
#             return validation_result

#         # Validate each window
#         for window_name, window_data in windows.items():
#             validation_result = self._validator.validate_window_fields(window_name, window_data)
#             if validation_result.get("status") == "error":
#                 return validation_result

#         # Process each window through obstruction → encoding workflow
#         results = {}
#         for window_name, window_data in windows.items():
#             result = self._process_single_window_encode(
#                 window_name=window_name,
#                 window_data=window_data,
#                 model_type=model_type,
#                 parameters=parameters,
#                 mesh=mesh
#             )
#             results[window_name] = result

#         # Check if any window processing failed
#         for window_name, result in results.items():
#             if result.get("status") == "error":
#                 self._logger.error(f"Window '{window_name}' encoding failed")
#                 return {
#                     "status": "error",
#                     "error": f"Window '{window_name}' encoding failed: {result.get('error')}",
#                     "partial_results": results
#                 }

#         self._logger.info("Encode workflow finished successfully")

#         # Return results with encoded images
#         return {
#             "status": "success",
#             "results": results
#         }
