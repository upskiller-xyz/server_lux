from typing import Dict, Any
from ....interfaces import ILogger
from ....enums import ResponseStatus, ResponseKey, RequestField
from ....exceptions import ServiceConnectionError, ServiceTimeoutError, ServiceResponseError, ServiceAuthorizationError
from ....constants import DeploymentMode
from ...obstruction import ObstructionCalculationService
from ...remote import EncoderService, ModelService
from .base_handler import WindowContext
from .obstruction_handler import ObstructionHandler
from .encoding_handler import EncodingHandler
from .simulation_handler import SimulationHandler
import os


class WindowProcessingChain:
    """Orchestrates window processing through handler chain

    Builds and executes Chain of Responsibility for window workflow.
    Handles error translation and context building.
    """

    def __init__(
        self,
        obstruction_service: ObstructionCalculationService,
        encoder_service: EncoderService,
        model_service: ModelService,
        logger: ILogger
    ):
        self._logger = logger
        self._chain = self._build_chain(
            obstruction_service,
            encoder_service,
            model_service,
            logger
        )

    def _build_chain(
        self,
        obstruction_service: ObstructionCalculationService,
        encoder_service: EncoderService,
        model_service: ModelService,
        logger: ILogger
    ) -> ObstructionHandler:
        """Build handler chain: Obstruction → Encoding → Simulation

        Returns:
            First handler in chain
        """
        # Create handlers
        obstruction_handler = ObstructionHandler(obstruction_service, encoder_service, logger)
        encoding_handler = EncodingHandler(encoder_service, logger)
        simulation_handler = SimulationHandler(model_service, logger)

        # Chain them together
        obstruction_handler.set_next(encoding_handler).set_next(simulation_handler)

        return obstruction_handler

    def process_window(
        self,
        window_name: str,
        window_data: Dict[str, Any],
        model_type: str,
        room_polygon: list,
        mesh: list,
        invert_channels: bool = False
    ) -> Dict[str, Any]:
        """Process single window through handler chain

        Args:
            window_name: Window identifier
            window_data: Window parameters
            model_type: Model type for encoding
            room_polygon: Room polygon
            mesh: Obstruction mesh
            invert_channels: Whether to invert image channels

        Returns:
            Processing result with window data and simulation result
        """
        self._logger.info(f"Processing window: {window_name}")

        try:
            # Build context
            context = self._build_context(
                window_name,
                window_data,
                model_type,
                room_polygon,
                mesh,
                invert_channels
            )

            # Execute chain
            result = self._chain.handle(context)

            # Check for processing errors
            if result.get(ResponseKey.STATUS.value) == ResponseStatus.ERROR.value:
                return self._build_error_result(window_name, result)

            # Build success result
            return self._build_success_result(window_name, window_data, context)

        except ServiceAuthorizationError as e:
            return self._handle_authorization_error(window_name, e)
        except ServiceConnectionError as e:
            return self._handle_connection_error(window_name, e)
        except ServiceTimeoutError as e:
            return self._handle_timeout_error(window_name, e)
        except ServiceResponseError as e:
            return self._handle_response_error(window_name, e)
        except Exception as e:
            return self._handle_generic_error(window_name, e)

    def _build_context(
        self,
        window_name: str,
        window_data: Dict[str, Any],
        model_type: str,
        room_polygon: list,
        mesh: list,
        invert_channels: bool
    ) -> WindowContext:
        """Build window context from request data"""
        return WindowContext(
            window_name=window_name,
            x1=window_data.get(RequestField.X1.value),
            y1=window_data.get(RequestField.Y1.value),
            z1=window_data.get(RequestField.Z1.value),
            x2=window_data.get(RequestField.X2.value),
            y2=window_data.get(RequestField.Y2.value),
            z2=window_data.get(RequestField.Z2.value),
            window_frame_ratio=window_data.get(RequestField.WINDOW_FRAME_RATIO.value),
            model_type=model_type,
            room_polygon=room_polygon,
            mesh=mesh,
            invert_channels=invert_channels
        )

    def _build_success_result(
        self,
        window_name: str,
        window_data: Dict[str, Any],
        context: WindowContext
    ) -> Dict[str, Any]:
        """Build success response with all window data"""
        return {
            ResponseKey.WINDOW_NAME.value: window_name,
            ResponseKey.STATUS.value: ResponseStatus.SUCCESS.value,
            ResponseKey.RESULT.value: context.simulation_result,
            RequestField.X1.value: window_data.get(RequestField.X1.value),
            RequestField.Y1.value: window_data.get(RequestField.Y1.value),
            RequestField.Z1.value: window_data.get(RequestField.Z1.value),
            RequestField.X2.value: window_data.get(RequestField.X2.value),
            RequestField.Y2.value: window_data.get(RequestField.Y2.value),
            RequestField.Z2.value: window_data.get(RequestField.Z2.value)
        }

    def _build_error_result(self, window_name: str, error_result: Dict[str, Any]) -> Dict[str, Any]:
        """Build error response"""
        error_result[ResponseKey.WINDOW_NAME.value] = window_name
        return error_result

    def _handle_authorization_error(self, window_name: str, e: ServiceAuthorizationError) -> Dict[str, Any]:
        """Handle authorization errors"""
        self._logger.error(f"[{window_name}] {e.get_log_message()}")
        return {
            ResponseKey.WINDOW_NAME.value: window_name,
            ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
            ResponseKey.ERROR.value: e.get_user_message(),
            ResponseKey.ERROR_TYPE.value: ResponseKey.AUTHORIZATION_ERROR.value
        }

    def _handle_connection_error(self, window_name: str, e: ServiceConnectionError) -> Dict[str, Any]:
        """Handle connection errors"""
        is_local = os.getenv(DeploymentMode.ENV_VAR, DeploymentMode.LOCAL) == DeploymentMode.LOCAL
        user_message = e.get_user_message(is_local)
        self._logger.error(f"[{window_name}] {e.get_log_message()}")

        return {
            ResponseKey.WINDOW_NAME.value: window_name,
            ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
            ResponseKey.ERROR.value: user_message,
            ResponseKey.ERROR_TYPE.value: ResponseKey.CONNECTION_ERROR.value
        }

    def _handle_timeout_error(self, window_name: str, e: ServiceTimeoutError) -> Dict[str, Any]:
        """Handle timeout errors"""
        self._logger.error(f"[{window_name}] {e.get_log_message()}")
        return {
            ResponseKey.WINDOW_NAME.value: window_name,
            ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
            ResponseKey.ERROR.value: f"Request timeout: {e.service_name} service did not respond within {e.timeout_seconds} seconds",
            ResponseKey.ERROR_TYPE.value: ResponseKey.TIMEOUT_ERROR.value
        }

    def _handle_response_error(self, window_name: str, e: ServiceResponseError) -> Dict[str, Any]:
        """Handle service response errors"""
        self._logger.error(f"[{window_name}] {e.get_log_message()}")
        return {
            ResponseKey.WINDOW_NAME.value: window_name,
            ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
            ResponseKey.ERROR.value: f"Service error: {e.service_name} returned status {e.status_code} - {e.error_message}",
            ResponseKey.ERROR_TYPE.value: ResponseKey.RESPONSE_ERROR.value
        }

    def _handle_generic_error(self, window_name: str, e: Exception) -> Dict[str, Any]:
        """Handle unexpected errors"""
        self._logger.error(f"[{window_name}] Processing failed: {str(e)}")
        return {
            ResponseKey.WINDOW_NAME.value: window_name,
            ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
            ResponseKey.ERROR.value: str(e)
        }
