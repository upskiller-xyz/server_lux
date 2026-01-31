from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import numpy as np

from src.server.services.helpers.parameter_validator import ParameterValidator
from ....enums import RequestField, ResponseKey


@dataclass
class WindowGeometry:
    """Window geometry interface"""
    x1: float
    y1: float
    z1: float
    x2: float
    y2: float
    z2: float
    window_frame_ratio: Optional[float] = None
    direction_angle: Optional[float] = None
    horizon: Optional[List[float]] = None
    zenith: Optional[List[float]] = None

    @classmethod
    def from_dict(cls, content: Dict[str, Any]) -> 'WindowGeometry':
        # Validate and extract required fields
        validated_params = cls._validate_required_fields(content)

        # Map standardized keys using enums
        validated_params[RequestField.DIRECTION_ANGLE.value] = content.get(RequestField.DIRECTION_ANGLE.value)
        validated_params[ResponseKey.HORIZON.value] = content.get(ResponseKey.HORIZON.value)
        validated_params[ResponseKey.ZENITH.value] = content.get(ResponseKey.ZENITH.value)

        return cls(**validated_params)

    @staticmethod
    def _validate_required_fields(content: Dict[str, Any]) -> Dict[str, float]:
        """Validate and extract required float fields

        Args:
            content: Dictionary containing window parameters

        Returns:
            Dictionary with validated float values

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Core required fields (x1, y1, z1, x2, y2, z2)
        core_required_fields = [
            RequestField.X1, RequestField.Y1, RequestField.Z1,
            RequestField.X2, RequestField.Y2, RequestField.Z2
        ]

        validated = {}
        for field in core_required_fields:
            value = content.get(field.value)
            if value is None:
                raise ValueError(f"Required field '{field.value}' is missing")
            try:
                validated[field.value] = float(value)
            except (TypeError, ValueError):
                raise ValueError(f"Field '{field.value}' must be a valid number, got {type(value).__name__}")

        # Optional window_frame_ratio field
        if RequestField.WINDOW_FRAME_RATIO.value in content:
            try:
                validated[RequestField.WINDOW_FRAME_RATIO.value] = float(content[RequestField.WINDOW_FRAME_RATIO.value])
            except (TypeError, ValueError):
                raise ValueError(f"Field 'window_frame_ratio' must be a valid number")

        return validated

    @property
    def to_dict(self) -> Dict[str, Any]:
        result = {
            RequestField.X1.value: self.x1,
            RequestField.Y1.value: self.y1,
            RequestField.Z1.value: self.z1,
            RequestField.X2.value: self.x2,
            RequestField.Y2.value: self.y2,
            RequestField.Z2.value: self.z2,
            RequestField.WINDOW_FRAME_RATIO.value: self.window_frame_ratio,
            RequestField.DIRECTION_ANGLE.value: self.direction_angle,
        }

        # Use standardized enum keys for obstruction angles
        if self.horizon is not None:
            result[ResponseKey.HORIZON.value] = self.horizon
        else:
            result[ResponseKey.HORIZON.value] = [0]

        if self.zenith is not None:
            result[ResponseKey.ZENITH.value] = self.zenith
        else:
            result[ResponseKey.ZENITH.value] = [0]

        return result

    def reference_point(self):
        return


@dataclass
class RoomPolygon:
    """Room polygon interface"""
    points: List[List[float]]


@dataclass
class Simulation:
    """Simulation result interface"""
    df_values: np.ndarray
    mask: Optional[np.ndarray] = None

    @property
    def has_mask(self) -> bool:
        return self.mask is not None


@dataclass
class EncoderParameters:
    """Encoder service parameters interface"""
    room_polygon: List[List[float]]
    windows: Dict[str, WindowGeometry]
