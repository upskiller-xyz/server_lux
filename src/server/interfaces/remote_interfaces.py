from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import numpy as np

from src.server.services.helpers.parameter_validator import ParameterValidator
from ..enums import RequestField, ResponseKey


# Domain models

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
    def from_dict(cls, content:Dict[str, Any])->'WindowGeometry':
        prms = {f.value: content.get(f.value) for f in ParameterValidator.REQUIRED_WINDOW_FIELDS}
        _opt_fields = [RequestField.DIRECTION_ANGLE, RequestField.OBSTRUCTION_ANGLE_HORIZON, RequestField.OBSTRUCTION_ANGLE_ZENITH]
        opt_prms = {f.value: content.get(f.value, None) for f in _opt_fields}
        prms.update(opt_prms)
        return cls(**prms)
    
    @property
    def to_dict(self)->Dict[str, Any]:
        return {
                RequestField.X1.value: self.x1,
                RequestField.Y1.value: self.y1,
                RequestField.Z1.value: self.z1,
                RequestField.X2.value: self.x2,
                RequestField.Y2.value: self.y2,
                RequestField.Z2.value: self.z2,
                RequestField.WINDOW_FRAME_RATIO.value: self.window_frame_ratio,
                RequestField.DIRECTION_ANGLE.value: self.direction_angle,
            
            }
    
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


# Base classes

@dataclass
class RemoteServiceRequest(ABC):
    """Base class for all remote service requests

    Encapsulates request parameters with type safety.
    Eliminates Dict[str, Any] in service calls.
    """

    @property
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary using enums"""
        pass

    def _build_dict(self, **kwargs) -> Dict[str, Any]:
        """Helper to build dictionary, filtering None values"""
        return {k: v for k, v in kwargs.items() if v is not None}

    @staticmethod
    def _array_to_list(arr: Optional[np.ndarray]) -> Optional[list]:
        """Convert numpy array to list for JSON serialization"""
        return arr.tolist() if arr is not None else None


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

    @abstractmethod
    def parse(self) -> Any:
        """Parse response data into typed structure"""
        pass

    def _get_required(self, key: str, error_msg: str = None) -> Any:
        if key not in self._raw:
            raise ValueError(error_msg or f"Missing required field: {key}")
        return self._raw[key]

    def _get_optional(self, key: str, default: Any = None) -> Any:
        return self._raw.get(key, default)


# Request types

# @dataclass
# class ColorManageRequest(RemoteServiceRequest):
#     """Request for color management operations"""
#     data: list
#     colorscale: str = "df"

#     @property
#     def to_dict(self) -> Dict[str, Any]:
#         return {
#             RequestField.DATA.value: self.data,
#             RequestField.COLORSCALE.value: self.colorscale
#         }

@dataclass
class Parameters(RemoteServiceRequest):
    """Request for obstruction angle calculations"""
    window: WindowGeometry
    room: RoomPolygon
    height_roof_over_floor: float=0
    floor_height_above_terrain: float=0
    simulation: Simulation|None = None
    result: Any = None

    @property
    def to_dict(self) -> Dict[str, Any]:
        return {
            RequestField.WINDOWS.value: self.window.to_dict,
            RequestField.FLOOR_HEIGHT.value: self.floor_height_above_terrain,
            RequestField.ROOF_HEIGHT.value: self.height_roof_over_floor,
            RequestField.ROOM_POLYGON.value: self.room.points
        }
    
    @classmethod
    def parse(cls, content:Dict[str, Any])->List['Parameters']:
        room = content.get(RequestField.ROOM_POLYGON.value, [])
        windows = content.get(RequestField.WINDOWS.value, {})
        wws = [WindowGeometry.from_dict(w) for w in windows]
        prms = [RequestField.ROOF_HEIGHT, RequestField.FLOOR_HEIGHT]
        opt_params = {p.value: content.get(p.value, None) for p in prms}
        return [cls(window=w, room=room, **opt_params) for w in wws]

@dataclass
class MainRequest(RemoteServiceRequest):
    """Request for obstruction angle calculations"""
    model_type: str
    params: Parameters
    mesh: list
    result: Any = None

    @property
    def to_dict(self) -> Dict[str, Any]:
        return {RequestField.MODEL_TYPE.value: self.model_type,
            RequestField.PARAMETERS.value: self.params,
            RequestField.MESH.value: self.mesh
        }
    
    @classmethod
    def parse(cls, content:Dict[str, Any])->List['MainRequest']:
        model_type = content.get(RequestField.MODEL_TYPE.value, "df_default")
        params = content.get(RequestField.PARAMETERS.value, {})
        prms = Parameters.parse(params)
        mesh = content.get(RequestField.MESH.value, [])
        return [cls(model_type, p, mesh) for p in prms]


@dataclass
class ObstructionRequest(RemoteServiceRequest):
    """Request for obstruction angle calculations"""
    x: float
    y: float
    z: float
    direction_angle: float
    mesh: list

    @classmethod
    def from_main(cls, main:MainRequest)->ObstructionRequest:
        center = main.window.reference_point
        return cls( , main.direction_angle, main.mesh)

    @property
    def to_dict(self) -> Dict[str, Any]:
        return {
            RequestField.X.value: self.x,
            RequestField.Y.value: self.y,
            RequestField.Z.value: self.z,
            RequestField.DIRECTION_ANGLE.value: self.direction_angle,
            RequestField.MESH.value: self.mesh
        }



    

@dataclass
class ModelRequest(RemoteServiceRequest):
    """Request for encoding operations"""
    model_type: str
    parameters: Dict[Any, Any]

    @property
    def to_dict(self) -> Dict[str, Any]:

        return {
            RequestField.MODEL_TYPE.value: self.model_type,
            RequestField.PARAMETERS.value: self.parameters
        }


@dataclass
class DirectionAngleRequest(RemoteServiceRequest):
    """Request for direction angle calculation"""
    parameters: Dict[str, Any]  # Contains room_polygon and windows

    @property
    def to_dict(self) -> Dict[str, Any]:
        return {RequestField.PARAMETERS.value: self.parameters}


@dataclass
class MergerRequest(RemoteServiceRequest):
    """Request for merging multiple window simulations"""
    room_polygon: List[List[float]]
    windows: Dict[str, WindowGeometry]
    simulations: Dict[str, Simulation]

    @property
    def to_dict(self) -> Dict[str, Any]:
        windows_dict = {}
        for window_name, window_geom in self.windows.items():
            windows_dict[window_name] = {
                RequestField.X1.value: window_geom.x1,
                RequestField.Y1.value: window_geom.y1,
                RequestField.Z1.value: window_geom.z1,
                RequestField.X2.value: window_geom.x2,
                RequestField.Y2.value: window_geom.y2,
                RequestField.Z2.value: window_geom.z2,
                RequestField.DIRECTION_ANGLE.value: window_geom.direction_angle
            }

        simulations_dict = {}
        for window_name, simulation in self.simulations.items():
            simulations_dict[window_name] = {
                RequestField.DF_VALUES.value: self._array_to_list(simulation.df_values),
                RequestField.MASK.value: self._array_to_list(simulation.mask)
            }

        return {
            RequestField.ROOM_POLYGON.value: self.room_polygon,
            RequestField.WINDOWS.value: windows_dict,
            RequestField.SIMULATIONS.value: simulations_dict
        }


@dataclass
class StatsRequest(RemoteServiceRequest):
    """Request for statistics calculation"""
    df_values: np.ndarray
    mask: np.ndarray

    @property
    def to_dict(self) -> Dict[str, Any]:
        return {
            RequestField.DF_VALUES.value: self._array_to_list(self.df_values),
            RequestField.MASK.value: self._array_to_list(self.mask)
        }


# Response types

class StandardResponse(RemoteServiceResponse):
    """Standard JSON response with status, data/error"""

    def parse(self) -> Dict[str, Any]:
        if self.is_error:
            raise ValueError(f"Service error: {self.error}")
        return self._raw


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


# class ColorManageResponse(StandardResponse):
#     """Response from color management operations"""

#     def parse(self) -> list:
#         if self.is_error:
#             raise ValueError(f"Color conversion error: {self.error}")
#         return self._get_optional(ResponseKey.DATA.value) or self._get_optional(ResponseKey.RESULT.value)


class ObstructionResponse(StandardResponse):
    """Response from obstruction calculations"""

    def parse(self) -> Dict[str, Any]:
        if self.is_error:
            raise ValueError(f"Obstruction calculation error: {self.error}")
        return self._get_required(ResponseKey.DATA.value)


class DirectionAngleResponse(StandardResponse):
    """Response from direction angle calculation"""

    def parse(self) -> Dict[str, float]:
        if self.is_error:
            raise ValueError(f"Direction angle calculation error: {self.error}")
        return self._get_required(ResponseKey.DIRECTION_ANGLES.value)


class MergerResponse(StandardResponse):
    """Response from merger service"""

    def parse(self) -> Dict[str, Any]:
        if self.is_error:
            raise ValueError(f"Merger error: {self.error}")

        df_matrix = self._get_optional(ResponseKey.RESULT.value) or self._get_optional(RequestField.DF_MATRIX.value)
        room_mask = self._get_optional(RequestField.MASK.value) or self._get_optional(RequestField.ROOM_MASK.value)

        return {
            RequestField.DF_MATRIX.value: df_matrix,
            RequestField.ROOM_MASK.value: room_mask
        }


class StatsResponse(StandardResponse):
    """Response from statistics calculation"""

    def parse(self) -> Dict[str, Any]:
        if self.is_error:
            raise ValueError(f"Statistics calculation error: {self.error}")
        return self._raw

