import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any
from ...remote.contracts import ObstructionRequest, ModelRequest
from ...remote.contracts import ObstructionResponse, EncoderResponse, ModelResponse
from ....enums import ResponseStatus, ResponseKey


@dataclass
class WindowContext:
    """Context passed through handler chain

    Encapsulates all data needed for window processing using typed request/response classes.
    Each handler enriches the context by:
    1. Using data from previous responses
    2. Creating new requests
    3. Storing responses for next handler
    """
    # Initial window parameters
    window_name: str
    x1: float
    y1: float
    z1: float
    x2: float
    y2: float
    z2: float
    window_frame_ratio: float
    model_type: str
    room_polygon: list
    mesh: list
    invert_channels: bool = False

    # Processing results (populated by handlers)
    direction_angle: Optional[float] = None

    # Typed request/response objects for sequential processing
    obstruction_response: Optional[ObstructionResponse] = None
    encoder_response: Optional[EncoderResponse] = None
    model_request: Optional[ModelRequest] = None
    model_response: Optional[ModelResponse] = None

    # Legacy fields (for backward compatibility during transition)
    horizon_angles: Optional[list] = None
    zenith_angles: Optional[list] = None
    encoded_image_bytes: Optional[bytes] = None
    mask_array: Optional[Any] = None
    simulation_result: Optional[dict] = None

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2

    @property
    def center_z(self) -> float:
        return (self.z1 + self.z2) / 2


class ProcessingHandler(ABC):
    """Base handler for Chain of Responsibility pattern

    Each handler processes one step of the workflow and passes to next.
    Follows Open/Closed Principle - extend without modifying.
    """

    def __init__(self, ):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._next_handler: Optional['ProcessingHandler'] = None

    def set_next(self, handler: 'ProcessingHandler') -> 'ProcessingHandler':
        """Chain handlers together

        Args:
            handler: Next handler in chain

        Returns:
            The handler that was set (for method chaining)
        """
        self._next_handler = handler
        return handler

    def handle(self, context: WindowContext) -> dict:
        """Execute this handler and pass to next

        Args:
            context: Window processing context

        Returns:
            Processing result or error
        """
        # Execute this handler's logic
        result = self._process(context)

        # If error, stop chain
        if result.get(ResponseKey.STATUS.value) == ResponseStatus.ERROR.value:
            return result

        # Continue to next handler if exists
        if self._next_handler:
            return self._next_handler.handle(context)

        # End of chain - return success
        return result

    @abstractmethod
    def _process(self, context: WindowContext) -> dict:
        """Process this step

        Args:
            context: Window processing context

        Returns:
            dict with status (success/error)
        """
        pass

    def _success(self) -> dict:
        """Build success response"""
        return {ResponseKey.STATUS.value: ResponseStatus.SUCCESS.value}

    def _error(self, message: str, error_type: str = None) -> dict:
        """Build error response

        Args:
            message: Error message
            error_type: Optional error type classification

        Returns:
            Error response dict
        """
        result = {
            ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
            ResponseKey.ERROR.value: message,
            ResponseKey.WINDOW_NAME.value: None  # Will be set by orchestrator
        }
        if error_type:
            result[ResponseKey.ERROR_TYPE.value] = error_type
        return result
