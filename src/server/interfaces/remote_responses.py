from abc import ABC
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import numpy as np
import base64

from ..enums import RequestField, ResponseKey, NPZKey


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
    direction_angle: float

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> 'DirectionAngleResponse':
        """Parse response data from direction angle service"""
        direction_angle = content.get(RequestField.DIRECTION_ANGLE.value, {})
        return cls(direction_angle=direction_angle)

    @property
    def to_dict(self) -> Dict[str, Any]:
        return {RequestField.DIRECTION_ANGLE.value: self.direction_angle}


@dataclass
class ReferencePointResponse:
    """Response from reference point calculation

    Returns the center point coordinates of a window.
    """
    x: float
    y: float
    z: float

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> 'ReferencePointResponse':
        """Parse response data from reference point calculation"""
        x = content.get(RequestField.X.value, 0)
        y = content.get(RequestField.Y.value, 0)
        z = content.get(RequestField.Z.value, 0)
        return cls(x, y, z)

    @property
    def to_dict(self) -> Dict[str, Any]:
        return {
            RequestField.X.value: self.x,
            RequestField.Y.value: self.y,
            RequestField.Z.value: self.z,
        }


@dataclass
class EncoderResponse:
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
        import io

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

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> 'ModelResponse':
        """Parse response data from model service"""

        # Get content (may be base64 encoded or already numpy)
        raw_content = content.get(ResponseKey.RESULT.value)
        shape = content.get("shape")

        if isinstance(raw_content, str):
            # Decode base64 to numpy array
            content_bytes = base64.b64decode(raw_content)
            result_array = np.frombuffer(content_bytes, dtype=np.float32)
            if shape:
                result_array = result_array.reshape(shape)
        elif isinstance(raw_content, (list, np.ndarray)):
            result_array = np.array(raw_content, dtype=np.float32)
            if shape is None:
                shape = list(result_array.shape)
        else:
            result_array = np.array([])

        return cls(content=result_array, shape=shape)

    @property
    def to_dict(self) -> Dict[str, Any]:
        return {
            ResponseKey.RESULT.value: self.content.tolist()
        }


@dataclass
class MergerResponse(StandardResponse):
    """Response from merger service

    Used for /merge endpoint to combine multiple window simulations.
    """
    result: np.ndarray
    mask: np.ndarray

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> 'MergerResponse':
        """Parse response data from merger service"""
        df_matrix = content.get(ResponseKey.RESULT.value) or content.get(RequestField.DF_MATRIX.value, [])
        room_mask = content.get(RequestField.MASK.value) or content.get(RequestField.ROOM_MASK.value, [])

        return cls(
            result=np.array(df_matrix, dtype=np.float32),
            mask=np.array(room_mask, dtype=np.float32)
        )

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
