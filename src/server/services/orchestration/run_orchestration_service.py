from typing import Dict, Any
from ...interfaces import ILogger
from ...enums import ResponseStatus, ResponseKey, RequestField
from ...constants import DefaultMaskValue
from ..obstruction import ObstructionCalculationService
from ..remote import EncoderService, ModelService, MergerService
from ..helpers.parameter_validator import ParameterValidator
from .handlers.window_processing_chain import WindowProcessingChain


class RunOrchestrationService:
    """Service for orchestrating complete run workflow

    Uses Chain of Responsibility pattern for window processing.
    Delegates validation to ParameterValidator.
    Each step extracted into focused handler classes.
    """

    def __init__(
        self,
        obstruction_calculation_service: ObstructionCalculationService,
        encoder_service: EncoderService,
        model_service: ModelService,
        merger_service: MergerService,
        logger: ILogger
    ):
        self._logger = logger
        self._merger = merger_service
        self._encoder = encoder_service
        self._validator = ParameterValidator()
        self._window_processor = WindowProcessingChain(
            obstruction_calculation_service,
            encoder_service,
            model_service,
            logger
        )

    def run_simulation(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute complete simulation workflow for all windows

        Validates → Processes windows → Merges results

        Args:
            request_data: Contains model_type, parameters with windows, and mesh

        Returns:
            Dictionary with merged results or error
        """
        self._logger.info("Starting run_simulation orchestration")

        # Validate request
        validation_result = self._validate_request(request_data)
        if validation_result:
            return validation_result

        # Extract parameters
        model_type, parameters, windows, mesh, invert_channels = self._extract_params(request_data)

        # Process all windows
        window_results = self._process_all_windows(
            windows,
            model_type,
            parameters,
            mesh,
            invert_channels
        )

        # Check for window processing errors
        error_result = self._check_window_errors(window_results)
        if error_result:
            return error_result

        # Merge results
        return self._merge_results(window_results, parameters, windows)

    def _validate_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate all request parameters

        Returns error dict if validation fails, None if success
        """
        model_type = request_data.get(RequestField.MODEL_TYPE.value)
        result = self._validator.validate_model_type(model_type)
        if result.get(ResponseKey.STATUS.value) == ResponseStatus.ERROR.value:
            return result

        parameters = request_data.get(RequestField.PARAMETERS.value, {})
        result = self._validator.validate_parameters(parameters)
        if result.get(ResponseKey.STATUS.value) == ResponseStatus.ERROR.value:
            return result

        windows = parameters.get(RequestField.WINDOWS.value, {})
        result = self._validator.validate_windows(windows)
        if result.get(ResponseKey.STATUS.value) == ResponseStatus.ERROR.value:
            return result

        mesh = request_data.get(RequestField.MESH.value)
        result = self._validator.validate_mesh(mesh)
        if result.get(ResponseKey.STATUS.value) == ResponseStatus.ERROR.value:
            return result

        # Validate each window
        for window_name, window_data in windows.items():
            result = self._validator.validate_window_fields(window_name, window_data)
            if result.get(ResponseKey.STATUS.value) == ResponseStatus.ERROR.value:
                return result

        return None

    def _extract_params(self, request_data: Dict[str, Any]) -> tuple:
        """Extract parameters from request"""
        model_type = request_data.get(RequestField.MODEL_TYPE.value)
        parameters = request_data.get(RequestField.PARAMETERS.value, {})
        windows = parameters.get(RequestField.WINDOWS.value, {})
        mesh = request_data.get(RequestField.MESH.value)
        invert_channels = parameters.get(RequestField.INVERT_CHANNELS.value, False)

        return model_type, parameters, windows, mesh, invert_channels

    def _process_all_windows(
        self,
        windows: Dict[str, Any],
        model_type: str,
        parameters: Dict[str, Any],
        mesh: list,
        invert_channels: bool
    ) -> Dict[str, Dict[str, Any]]:
        """Process all windows through handler chain"""
        room_polygon = parameters.get(RequestField.ROOM_POLYGON.value)
        results = {}

        for window_name, window_data in windows.items():
            result = self._window_processor.process_window(
                window_name=window_name,
                window_data=window_data,
                model_type=model_type,
                room_polygon=room_polygon,
                mesh=mesh,
                invert_channels=invert_channels
            )
            results[window_name] = result

        return results

    def _check_window_errors(self, window_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Check if any window processing failed

        Returns error dict if failures found, None otherwise
        """
        for window_name, result in window_results.items():
            if result.get(ResponseKey.STATUS.value) == ResponseStatus.ERROR.value:
                self._logger.error(f"Window '{window_name}' processing failed, skipping merger")
                return {
                    ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                    ResponseKey.ERROR.value: f"Window '{window_name}' processing failed: {result.get(ResponseKey.ERROR.value)}",
                    ResponseKey.PARTIAL_RESULTS.value: window_results
                }
        return None

    def _merge_results(
        self,
        window_results: Dict[str, Dict[str, Any]],
        parameters: Dict[str, Any],
        windows: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge all window results into room-level data"""
        self._logger.info("Starting merger service to combine all window results")
        room_polygon = parameters.get(RequestField.ROOM_POLYGON.value)

        # Prepare merger inputs
        windows_for_merger = self._prepare_windows_for_merger(windows, room_polygon)
        simulations_for_merger = self._prepare_simulations_for_merger(window_results)

        # Execute merger
        try:
            merger_result = self._merger.run(
                room_polygon=room_polygon,
                windows=windows_for_merger,
                simulations=simulations_for_merger
            )

            if merger_result.get(ResponseKey.STATUS.value) == ResponseStatus.ERROR.value:
                return self._build_merger_error(merger_result, window_results)

            return self._build_success_response(merger_result, window_results)

        except Exception as e:
            self._logger.error(f"Merger service error: {str(e)}")
            return self._build_merger_exception(e, window_results)

    def _prepare_windows_for_merger(
        self,
        windows: Dict[str, Any],
        room_polygon: list
    ) -> Dict[str, Dict[str, Any]]:
        """Extract window positions and direction angles for merger"""
        windows_for_merger = {}

        for window_name, window_data in windows.items():
            direction_angle = self._get_direction_angle(window_name, window_data, room_polygon)

            windows_for_merger[window_name] = {
                RequestField.X1.value: window_data.get(RequestField.X1.value),
                RequestField.Y1.value: window_data.get(RequestField.Y1.value),
                RequestField.Z1.value: window_data.get(RequestField.Z1.value),
                RequestField.X2.value: window_data.get(RequestField.X2.value),
                RequestField.Y2.value: window_data.get(RequestField.Y2.value),
                RequestField.Z2.value: window_data.get(RequestField.Z2.value),
                RequestField.DIRECTION_ANGLE.value: direction_angle
            }

        return windows_for_merger

    def _get_direction_angle(
        self,
        window_name: str,
        window_data: Dict[str, Any],
        room_polygon: list
    ) -> float:
        """Get direction angle for window"""
        if RequestField.DIRECTION_ANGLE.value in window_data:
            return window_data[RequestField.DIRECTION_ANGLE.value]

        # Calculate from encoder service
        calc_params = {
            RequestField.ROOM_POLYGON.value: room_polygon,
            RequestField.WINDOWS.value: {
                window_name: {
                    RequestField.X1.value: window_data.get(RequestField.X1.value),
                    RequestField.Y1.value: window_data.get(RequestField.Y1.value),
                    RequestField.X2.value: window_data.get(RequestField.X2.value),
                    RequestField.Y2.value: window_data.get(RequestField.Y2.value)
                }
            }
        }
        direction_result = self._encoder.calculate_direction_angles(calc_params)
        return direction_result.get(ResponseKey.DIRECTION_ANGLES.value, {}).get(window_name, 0)

    def _prepare_simulations_for_merger(
        self,
        window_results: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Extract simulation data and masks for merger"""
        simulations = {}

        for window_name, result in window_results.items():
            simulation_result = result.get(ResponseKey.RESULT.value, {})
            df_values, mask = self._parse_simulation_result(simulation_result)

            if mask is None:
                mask = self._create_default_mask(df_values)

            simulations[window_name] = {
                RequestField.DF_VALUES.value: df_values,
                RequestField.MASK.value: mask
            }

        return simulations

    def _parse_simulation_result(self, simulation_result: Dict[str, Any]) -> tuple:
        """Parse simulation result using adapter-map pattern"""
        # Format 1: Prediction field
        if ResponseKey.PREDICTION.value in simulation_result:
            return (
                simulation_result[ResponseKey.PREDICTION.value],
                simulation_result.get(RequestField.MASK.value)
            )

        # Format 2: Data field
        if ResponseKey.DATA.value in simulation_result:
            data_field = simulation_result[ResponseKey.DATA.value]
            if isinstance(data_field, dict):
                return (
                    data_field.get(RequestField.DF_VALUES.value, data_field),
                    data_field.get(RequestField.MASK.value)
                )
            return (data_field, None)

        # Format 3: Direct fields
        return (
            simulation_result.get(RequestField.DF_VALUES.value, []),
            simulation_result.get(RequestField.MASK.value)
        )

    def _create_default_mask(self, df_values: list) -> list:
        """Create default mask matching df_values shape"""
        if isinstance(df_values, list) and len(df_values) > 0:
            return [[DefaultMaskValue.FILL_VALUE for _ in row] for row in df_values]
        return []

    def _build_success_response(
        self,
        merger_result: Dict[str, Any],
        window_results: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build success response with merged data"""
        self._logger.info("Complete workflow finished successfully with merger")
        return {
            ResponseKey.STATUS.value: ResponseStatus.SUCCESS.value,
            ResponseKey.WINDOW_RESULTS.value: window_results,
            ResponseKey.MERGED_RESULT.value: {
                RequestField.DF_MATRIX.value: merger_result.get(ResponseKey.RESULT.value, merger_result.get(RequestField.DF_MATRIX.value)),
                RequestField.ROOM_MASK.value: merger_result.get(RequestField.MASK.value, merger_result.get(RequestField.ROOM_MASK.value))
            }
        }

    def _build_merger_error(
        self,
        merger_result: Dict[str, Any],
        window_results: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build error response for merger failure"""
        self._logger.error("Merger service failed")
        return {
            ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
            ResponseKey.ERROR.value: f"Merger failed: {merger_result.get(ResponseKey.ERROR.value)}",
            ResponseKey.WINDOW_RESULTS.value: window_results
        }

    def _build_merger_exception(
        self,
        exception: Exception,
        window_results: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build response for merger exception"""
        return {
            ResponseKey.STATUS.value: ResponseStatus.SUCCESS.value,
            ResponseKey.WINDOW_RESULTS.value: window_results,
            ResponseKey.MERGER_ERROR.value: str(exception)
        }
