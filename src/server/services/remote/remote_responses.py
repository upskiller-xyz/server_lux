from abc import ABC
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import numpy as np
import base64
import io

from ...enums import RequestField, ResponseKey, NPZKey


# Base classes

class RemoteServiceResponse(ABC):
    """Base class for all remote service responses

    Parses response data into typed structures.
    """

    def __init__(self, raw_response: Dict[str, Any]):
        self._raw = raw_response
        self.status = raw_response.get(ResponseKey.STATUS.value)
        self.error = raw_response.get(ResponseKey.ERROR.value)

    @property
    def is_success(self) -> bool:
        return self.status == ResponseKey.SUCCESS.value

    @property
    def is_error(self) -> bool:
        return self.status == ResponseKey.ERROR.value

    def _get_required(self, key: str, error_msg: str = None) -> Any:
        if key not in self._raw:
            raise ValueError(error_msg or f"Missing required field: {key}")
        return self._raw[key]

    def _get_optional(self, key: str, default: Any = None) -> Any:
        return self._raw.get(key, default)

    def parse(self) -> Dict[str, Any]:
        """Default parse method - return raw response

        Override in subclasses for custom parsing logic.
        """
        return self._raw


# Response types
#
# Available response classes:
# - ObstructionResponse: Obstruction angle calculation results (single or multi-direction)
# - DirectionAngleResponse: Direction angle calculation results
# - ReferencePointResponse: Reference point coordinates
# - EncoderResponse: Encoded room images (NPZ format with image/mask arrays)
# - ModelResponse: Model/simulation results (numpy arrays)
# - MergerResponse: Merged window simulation results
# - StatsResponse: Statistics calculation results
# - BinaryResponse: Raw binary data responses
# - StandardResponse: Generic JSON responses (fallback)


class StandardResponse(RemoteServiceResponse):
    """Standard JSON response with status, data/error"""

    @classmethod
    def parse(cls, content: Dict[Any, Any]) -> 'StandardResponse':
        return cls(content)


class BinaryResponse(RemoteServiceResponse):
    """Binary data response (e.g., PNG images)"""

    def __init__(self, raw_data: bytes):
        self._binary_data = raw_data
        super().__init__({})

    @property
    def is_success(self) -> bool:
        return self._binary_data is not None

    def parse(self) -> bytes:
        return self._binary_data


@dataclass
class ObstructionResponse(StandardResponse):
    """Response from obstruction calculations

    Used for /horizon_angle, /zenith_angle, /obstruction, /obstruction_multi,
    and /obstruction_parallel endpoints.

    Standardized: only horizon_angle and zenith_angle (can be float or List[float]).
    """
    horizon_angle: Optional[float | List[float]] = None
    zenith_angle: Optional[float | List[float]] = None

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> 'ObstructionResponse':
        """Parse response data from obstruction service

        Handles both single values and arrays, normalizing to horizon_angle/zenith_angle.
        """
        # Try single values first
        horizon_angle = content.get(RequestField.OBSTRUCTION_ANGLE_HORIZON.value)
        zenith_angle = content.get(RequestField.OBSTRUCTION_ANGLE_ZENITH.value)

        return cls(
            horizon_angle=horizon_angle,
            zenith_angle=zenith_angle
        )

    @property
    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if self.horizon_angle is not None:
            result[ResponseKey.HORIZON_ANGLE.value] = self.horizon_angle
        if self.zenith_angle is not None:
            result[ResponseKey.ZENITH_ANGLE.value] = self.zenith_angle
        return result


@dataclass
class DirectionAngleResponse(StandardResponse):
    """Response from direction angle calculation

    Used for /calculate-direction endpoint.
    """
    direction_angle: Dict[str, float] = None

    def __init__(self, raw_response: Dict[str, Any]):
        """Initialize from raw response"""
        super().__init__(raw_response)
        self.direction_angles = raw_response.get(ResponseKey.DIRECTION_ANGLE.value, {})
        self.direction_angles_degrees = raw_response.get(ResponseKey.DIRECTION_ANGLE.value, {})

    def parse(self) -> Dict[str, Any]:
        """Parse response data from direction angle service"""
        return {
            ResponseKey.DIRECTION_ANGLE.value: self.direction_angles
        }

    @property
    def to_dict(self) -> Dict[str, Any]:
        return {
            ResponseKey.DIRECTION_ANGLE.value: self.direction_angle
        }


@dataclass
class ReferencePointResponse(StandardResponse):
    """Response from reference point calculation

    Returns the center point coordinates for each window.

    Expected format:
    {
        "reference_point": {
            "window_id": {"x": 0.0, "y": 0.0, "z": 1.75}
        }
    }
    """
    reference_point: Dict[str, Dict[str, float]]

    def __init__(self, raw_response: Dict[str, Any]):
        """Initialize from raw response"""
        super().__init__(raw_response)
        self.reference_point = raw_response.get(RequestField.REFERENCE_POINT.value, {})

    def parse(self) -> Dict[str, Any]:
        """Parse response and return reference points"""
        return {
            RequestField.REFERENCE_POINT.value: self.reference_point
        }

    @property
    def to_dict(self) -> Dict[str, Any]:
        return {
            RequestField.REFERENCE_POINT.value: self.reference_point
        }


@dataclass
class EncoderResponse(StandardResponse):
    """Response from encoder service

    Used for /encode endpoint. Returns encoded image and mask as numpy arrays.
    For now, handles one window at a time.
    """
    image: np.ndarray
    mask: np.ndarray

    @classmethod
    def parse(cls, response_content: bytes) -> 'EncoderResponse':
        """Parse NPZ response data from encoder service

        The encoder returns an NPZ file with keys like 'window_name_image' and 'window_name_mask'.
        For now, we process one window at a time and extract the first image/mask pair.

        Args:
            response_content: Raw bytes from response.content (NPZ format)

        Returns:
            EncoderResponse with image and mask arrays
        """
        

        npz_data = np.load(io.BytesIO(response_content))
        keys = list(npz_data.keys())

        # Find keys ending with 'image' and 'mask'
        image_keys = [k for k in keys if k.endswith(NPZKey.IMAGE_SUFFIX.value)]
        mask_keys = [k for k in keys if k.endswith(NPZKey.MASK_SUFFIX.value)]

        # For now, take the first window (index 0)
        # TODO: Support multiple windows when needed
        image_key = image_keys[0] if image_keys else None
        mask_key = mask_keys[0] if mask_keys else None

        if not image_key or not mask_key:
            raise ValueError(f"Could not find image/mask keys in NPZ. Available keys: {keys}")

        image = npz_data[image_key]
        mask = npz_data[mask_key]

        return cls(image=image, mask=mask)

    @property
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with lists for JSON serialization"""
        return {
            NPZKey.IMAGE.value: self.image.tolist(),
            NPZKey.MASK.value: self.mask.tolist()
        }


@dataclass
class ModelResponse(StandardResponse):
    """Response from model/simulation service

    Used for /simulate, /get_df, and related endpoints.
    """
    content: np.ndarray
    shape: Optional[List[int]] = None
    mask: Optional[np.ndarray] = None

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> Dict[str, Any]:
        """Parse response data from model service

        Returns dict with 'simulation', 'shape', and 'mask' keys for orchestration.
        """
        raw_content = content.get(ResponseKey.RESULT.value)
        shape = content.get(RequestField.SHAPE.value)
        raw_mask = content.get(RequestField.MASK.value)
        
        result_array = cls._parse_simulation(raw_content, shape)
        mask_array = cls._parse_mask(raw_mask)

        return {
            RequestField.SIMULATION.value: result_array.tolist(),
            RequestField.MASK.value: mask_array.tolist() if mask_array is not None else None,
            ResponseKey.STATUS.value: content.get(ResponseKey.STATUS.value, ResponseKey.SUCCESS.value)
        }
    @classmethod
    def _parse_simulation(cls, raw_content:Any, shape:list[int] | None=None):
        if isinstance(raw_content, str):
            content_bytes = base64.b64decode(raw_content)
            result_array = np.frombuffer(content_bytes, dtype=np.float32)
            if shape:
                return result_array.reshape(shape)
        elif isinstance(raw_content, (list, np.ndarray)):
            return np.array(raw_content, dtype=np.float32)
        else:
            return np.array([])
        
    @classmethod
    def _parse_mask(cls, raw_mask:Any, shape:list[int] | None=None):
        mask_array = None
        if raw_mask is not None:
            if isinstance(raw_mask, str):
                mask_bytes = base64.b64decode(raw_mask)
                mask_array = np.frombuffer(mask_bytes, dtype=np.float32)
                if shape:
                    mask_array = mask_array.reshape(shape)
                return mask_array
            elif isinstance(raw_mask, (list, np.ndarray)):
                return np.array(raw_mask, dtype=np.float32)


    @property
    def to_dict(self) -> Dict[str, Any]:
        result = {
            ResponseKey.RESULT.value: self.content.tolist()
        }
        if self.mask is not None:
            result[RequestField.MASK.value] = self.mask.tolist()
        return result


@dataclass
class MergerResponse(StandardResponse):
    """Response from merger service

    Used for /merge endpoint to combine multiple window simulations.
    """
    result: np.ndarray
    mask: np.ndarray

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> Dict[str, Any]:
        """Parse response data from merger service

        Returns dict for consistency with orchestration flow.
        """
        df_matrix = content.get(ResponseKey.RESULT.value) or content.get(RequestField.DF_MATRIX.value, [])
        room_mask = content.get(RequestField.MASK.value) or content.get(RequestField.ROOM_MASK.value, [])

        # Return dict (not MergerResponse object) for orchestration
        return {
            RequestField.RESULT.value: df_matrix,
            RequestField.MASK.value: room_mask
        }

    @property
    def to_dict(self) -> Dict[str, Any]:
        return {
            RequestField.DF_MATRIX.value: self.result.tolist(),
            RequestField.ROOM_MASK.value: self.mask.tolist()
        }


@dataclass
class StatsResponse(StandardResponse):
    """Response from statistics calculation

    Used for /get_stats and /calculate endpoints.
    """
    statistics: Dict[str, Any]

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> 'StatsResponse':
        """Parse response data from statistics service

        Returns all statistics data from the response.
        """
        # Remove status/error keys to get just the statistics
        stats = {k: v for k, v in content.items()
                if k not in [ResponseKey.STATUS.value, ResponseKey.ERROR.value]}

        return cls(statistics=stats)

    @property
    def to_dict(self) -> Dict[str, Any]:
        return self.statistics
