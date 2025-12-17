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


# Request types
#
# Available request classes:
# - MainRequest: Main external /simulate endpoint request
# - Parameters: Shared parameter structure for room/window configuration
# - ObstructionRequest: Single point obstruction calculation (/horizon_angle, /zenith_angle, /obstruction)
# - ObstructionMultiRequest: Multi-direction obstruction calculation (/obstruction_multi)
# - ObstructionParallelRequest: Parallel obstruction calculation (/obstruction_parallel)
# - DirectionAngleRequest: Direction angle calculation (/calculate-direction)
# - MergerRequest: Window simulation merging (/merge)
# - StatsRequest: Statistics calculation (/get_stats, /calculate)
# - ModelRequest: Encoding operations (/encode, /encode_raw)

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
    """Request for obstruction angle calculations (single point and direction)

    Used for /horizon_angle, /zenith_angle, and /obstruction endpoints.
    """
    x: float
    y: float
    z: float
    direction_angle: float
    mesh: List[List[float]]

    @classmethod
    def from_main(cls, main: MainRequest) -> 'ObstructionRequest':
        center = (0,0,0) # main.params.window.reference_point()
        return cls(
            x=center[0],
            y=center[1],
            z=center[2],
            direction_angle=main.params.window.direction_angle,
            mesh=main.mesh
        )

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
class ObstructionMultiRequest(RemoteServiceRequest):
    """Request for multi-direction obstruction angle calculations

    Used for /obstruction_multi endpoint to calculate multiple directions
    across a half-circle centered on the window normal.
    """
    x: float
    y: float
    z: float
    direction_angle: float
    mesh: List[List[float]]
    start_angle: Optional[float] = None
    end_angle: Optional[float] = None
    num_directions: Optional[int] = None

    @property
    def to_dict(self) -> Dict[str, Any]:
        return self._build_dict(
            **{
                RequestField.X.value: self.x,
                RequestField.Y.value: self.y,
                RequestField.Z.value: self.z,
                RequestField.DIRECTION_ANGLE.value: self.direction_angle,
                RequestField.MESH.value: self.mesh,
                RequestField.START_ANGLE.value: self.start_angle,
                RequestField.END_ANGLE.value: self.end_angle,
                RequestField.NUM_DIRECTIONS.value: self.num_directions
            }
        )


@dataclass
class ObstructionParallelRequest(RemoteServiceRequest):
    """Request for parallel obstruction angle calculations

    Used for /obstruction_parallel endpoint to calculate all directions
    using optimized parallel processing.
    """
    x: float
    y: float
    z: float
    direction_angle: float
    mesh: List[List[float]]

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
    """Request for direction angle calculation

    Used for /calculate-direction endpoint to calculate direction angles
    for windows in a room based on room polygon and window positions.
    """
    room_polygon: List[List[float]]
    windows: Dict[str, WindowGeometry]

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
                RequestField.Z2.value: window_geom.z2
            }

        return {
            RequestField.PARAMETERS.value: {
                RequestField.ROOM_POLYGON.value: self.room_polygon,
                RequestField.WINDOWS.value: windows_dict
            }
        }


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
            RequestField.SIMULATION.value: simulations_dict
        }


@dataclass
class StatsRequest(RemoteServiceRequest):
    """Request for statistics calculation

    Used for /get_stats and /calculate endpoints to compute daylight statistics
    from simulation results with an optional mask.
    """
    df_values: np.ndarray
    mask: Optional[np.ndarray] = None

    @property
    def to_dict(self) -> Dict[str, Any]:
        return self._build_dict(
            **{
                RequestField.DF_VALUES.value: self._array_to_list(self.df_values),
                RequestField.MASK.value: self._array_to_list(self.mask)
            }
        )

