from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import numpy as np

from src.server.services.helpers.parameter_validator import ParameterValidator
from ....enums import RequestField


@dataclass
class WindowGeometry:
    """Window geometry interface"""
    x1: float
    y1: float
    z1: float
    x2: float
    y2: float
    z2: float
    window_frame_ratio: float
    direction_angle: Optional[float] = None
    obstruction_angle_horizon: Optional[List[float]] = None
    obstruction_angle_zenith: Optional[List[float]] = None

    @classmethod
    def from_dict(cls, content: Dict[str, Any]) -> 'WindowGeometry':
        prms = {f.value: content.get(f.value) for f in ParameterValidator.REQUIRED_WINDOW_FIELDS}
        _opt_fields = [RequestField.DIRECTION_ANGLE, RequestField.OBSTRUCTION_ANGLE_HORIZON, RequestField.OBSTRUCTION_ANGLE_ZENITH]
        opt_prms = {f.value: content.get(f.value, None) for f in _opt_fields}
        prms.update(opt_prms)
        return cls(**prms)

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

        if self.obstruction_angle_horizon is not None:
            result[RequestField.OBSTRUCTION_ANGLE_HORIZON.value] = self.obstruction_angle_horizon
        if not self.obstruction_angle_horizon:
            result[RequestField.OBSTRUCTION_ANGLE_HORIZON.value] = [0]
        if self.obstruction_angle_zenith is not None:
            result[RequestField.OBSTRUCTION_ANGLE_ZENITH.value] = self.obstruction_angle_zenith
        if not self.obstruction_angle_horizon:
            result[RequestField.OBSTRUCTION_ANGLE_ZENITH.value] = [0]

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
