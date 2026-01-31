from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import numpy as np

from src.server.services.helpers.parameter_validator import ParameterValidator
from ...enums import RequestField, ResponseKey


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
    horizon: Optional[List[float]] = None
    zenith: Optional[List[float]] = None

    @classmethod
    def from_dict(cls, content:Dict[str, Any])->'WindowGeometry':
        prms = {f.value: content.get(f.value) for f in ParameterValidator.REQUIRED_WINDOW_FIELDS}
        _opt_fields = [RequestField.DIRECTION_ANGLE, RequestField.HORIZON, RequestField.ZENITH]
        opt_prms = {f.value: content.get(f.value, None) for f in _opt_fields}
        prms.update(opt_prms)
        return cls(**prms)
    
    @property
    def to_dict(self)->Dict[str, Any]:
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

        if self.horizon is not None:
            result[RequestField.HORIZON.value] = self.horizon
        else:
            result[RequestField.HORIZON.value] = [0]

        if self.zenith is not None:
            result[RequestField.ZENITH.value] = self.zenith
        else:
            result[RequestField.ZENITH.value] = [0]

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
    window_name: str = "window"  # Store window name for serialization

    @property
    def to_dict(self) -> Dict[str, Any]:
        return {
            RequestField.WINDOWS.value: {self.window_name: self.window.to_dict},
            RequestField.FLOOR_HEIGHT.value: self.floor_height_above_terrain,
            RequestField.ROOF_HEIGHT.value: self.height_roof_over_floor,
            RequestField.ROOM_POLYGON.value: self.room.points
        }

    @classmethod
    def parse(cls, content:Dict[str, Any])->List['Parameters']:

        room_points = content.get(RequestField.ROOM_POLYGON.value, [])
        room = RoomPolygon(points=room_points)
        windows = content.get(RequestField.WINDOWS.value, {})

        # Get obstruction angles and other computed values from orchestration
        obstruction_horizon_raw = content.get(RequestField.HORIZON.value, {})
        obstruction_zenith_raw = content.get(RequestField.ZENITH.value, {})
        direction_angles_raw = content.get(RequestField.DIRECTION_ANGLE.value, {})
        
        wws = []
        if isinstance(windows, dict):
            wws = cls._parse_window_dict(windows, obstruction_horizon_raw, obstruction_zenith_raw, direction_angles_raw)
        elif isinstance(windows, list):
            wws = cls._parse_window_list(windows)
           

        prms = [RequestField.ROOF_HEIGHT, RequestField.FLOOR_HEIGHT]
        opt_params = {p.value: content.get(p.value, None) for p in prms}
        return [cls(window=w, room=room, window_name=name, **opt_params) for name, w in wws]
    
    @classmethod
    def _parse_window_dict(cls, windows:dict[Any:Any], obstruction_horizon_raw={}, obstruction_zenith_raw={}, direction_angles_raw={})->list[tuple[str, WindowGeometry]]:
        wws = []
        obstruction_horizon = cls._normalize_to_dict(obstruction_horizon_raw)
        obstruction_zenith = cls._normalize_to_dict(obstruction_zenith_raw)
        direction_angles_dict = cls._normalize_to_dict(direction_angles_raw)

        for name, w in windows.items():
            window_geom = WindowGeometry.from_dict(w)
            if name in obstruction_horizon:
                window_geom.horizon = obstruction_horizon[name]
            if name in obstruction_zenith:
                window_geom.zenith = obstruction_zenith[name]
            if name in direction_angles_dict:
                window_geom.direction_angle = direction_angles_dict[name]
            wws.append((name, window_geom))
        return wws
    
    @classmethod
    def _parse_window_list(cls, windows:list[dict[Any:Any]])->list[tuple[str, WindowGeometry]]:
        return [(f"window_{i}", WindowGeometry.from_dict(w)) for i, w in enumerate(windows)]
    
    @classmethod
    def _normalize_to_dict(cls, field):
        return field if isinstance(field, dict) else {}

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
            RequestField.PARAMETERS.value: self.params.to_dict,
            RequestField.MESH.value: self.mesh
        }
    
    @classmethod
    def parse(cls, content:Dict[str, Any])->List['MainRequest']:
        model_type = content.get(RequestField.MODEL_TYPE.value, "df_default")
        params_dict = content.get(RequestField.PARAMETERS.value, {})

        # Merge accumulated orchestration data (from top-level) with parameters
        # This allows Parameters.parse() to access reference_point, direction_angle, obstruction_angle_*, etc.
        merged_params = params_dict.copy()
        for key in [RequestField.REFERENCE_POINT.value, RequestField.DIRECTION_ANGLE.value,
                   RequestField.OBSTRUCTION_ANGLE_HORIZON.value, RequestField.OBSTRUCTION_ANGLE_ZENITH.value]:
            if key in content:
                merged_params[key] = content[key]

        prms = Parameters.parse(merged_params)
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
    window_name: str = "window"  # Store window name for response mapping

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> List['ObstructionRequest']:
        """Parse dictionary into list of ObstructionRequest (one per window)

        Args:
            content: Dictionary with required fields, optionally including
                    reference_point and direction_angle dicts from previous services

        Returns:
            List of ObstructionRequest instances (one per window)
        """
        # Check if this is a simple single-window request
        if RequestField.X.value in content:
            # Direct format with x, y, z
            return [cls(
                x=content.get(RequestField.X.value),
                y=content.get(RequestField.Y.value),
                z=content.get(RequestField.Z.value),
                direction_angle=content.get(RequestField.DIRECTION_ANGLE.value),
                mesh=content.get(RequestField.MESH.value, [])
            )]

        # Otherwise, extract from reference_point and direction_angle responses
        reference_points = content.get(RequestField.REFERENCE_POINT.value, {})
        direction_angles = content.get(RequestField.DIRECTION_ANGLE.value, {})
        mesh = content.get(RequestField.MESH.value, [])

        requests = []
        for window_name, ref_point in reference_points.items():
            direction_angle = direction_angles.get(window_name, 0.0)
            requests.append(cls(
                x=ref_point.get(RequestField.X.value, 0.0),
                y=ref_point.get(RequestField.Y.value, 0.0),
                z=ref_point.get(RequestField.Z.value, 0.0),
                direction_angle=direction_angle,
                mesh=mesh,
                window_name=window_name  # Preserve window name
            ))

        return requests

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
    """Request for model inference (simulation)

    Expects image data from encoder service in the image field.
    """
    image: bytes  # Binary image data from encoder
    filename: str = "image.png"
    invert_channels: bool = False

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> List['ModelRequest']:
        """Parse dictionary into ModelRequest

        Args:
            content: Dictionary with 'image' field containing binary image data

        Returns:
            List with single ModelRequest instance
        """
        image_data = content.get(RequestField.IMAGE.value)
        if not image_data:
            raise ValueError("Missing 'image' field in request data for ModelService")

        return [cls(
            image=image_data,
            filename=content.get('filename', 'image.png')
        )]

    @property
    def to_dict(self) -> Dict[str, Any]:
        # Model service doesn't use to_dict, it uploads multipart
        return {
            RequestField.IMAGE.value: self.image,
            'filename': self.filename
        }


@dataclass
class DirectionAngleRequest(RemoteServiceRequest):
    """Request for direction angle calculation

    Used for /calculate-direction endpoint to calculate direction angles
    for windows in a room based on room polygon and window positions.
    """
    room_polygon: List[List[float]]
    windows: Dict[str, WindowGeometry]

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> List['DirectionAngleRequest']:
        """Parse dictionary into list of DirectionAngleRequest (one per window)

        Args:
            content: Dictionary with 'room_polygon' and 'windows' keys,
                    or with 'parameters' key containing room_polygon and windows

        Returns:
            List of DirectionAngleRequest instances (one per window)
        """
        # Check if data is nested in 'parameters' (from /encode or /run endpoints)
        if RequestField.PARAMETERS.value in content:
            content = content.get(RequestField.PARAMETERS.value, {})
            
        room_polygon = content.get(RequestField.ROOM_POLYGON.value, [])
        windows_dict = content.get(RequestField.WINDOWS.value, {})

        # Create one request per window
        requests = []
        for window_name, window_data in windows_dict.items():
            window_geom = WindowGeometry.from_dict(window_data)
            requests.append(cls(
                room_polygon=room_polygon,
                windows={window_name: window_geom}
            ))

        return requests

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
            RequestField.ROOM_POLYGON.value: self.room_polygon,
            RequestField.WINDOWS.value: windows_dict
        }


@dataclass
class ReferencePointRequest(RemoteServiceRequest):
    """Request for reference point calculation

    Used for /get-reference-point endpoint to calculate reference points
    for windows in a room based on room polygon and window positions.
    """
    room_polygon: List[List[float]]
    windows: Dict[str, WindowGeometry]

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> List['ReferencePointRequest']:
        """Parse dictionary into list of ReferencePointRequest (one per window)

        Args:
            content: Dictionary with 'room_polygon' and 'windows' keys,
                    or with 'parameters' key containing room_polygon and windows

        Returns:
            List of ReferencePointRequest instances (one per window)
        """
        # Check if data is nested in 'parameters' (from /encode or /run endpoints)
        if RequestField.PARAMETERS.value in content:
            content = content.get(RequestField.PARAMETERS.value, {})
        room_polygon = content.get(RequestField.ROOM_POLYGON.value, [])
        windows_dict = content.get(RequestField.WINDOWS.value, {})

        # Create one request per window
        requests = []
        for window_name, window_data in windows_dict.items():
            window_geom = WindowGeometry.from_dict(window_data)
            requests.append(cls(
                room_polygon=room_polygon,
                windows={window_name: window_geom}
            ))

        return requests

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
            RequestField.ROOM_POLYGON.value: self.room_polygon,
            RequestField.WINDOWS.value: windows_dict
        }


@dataclass
class MergerRequest(RemoteServiceRequest):
    """Request for merging multiple window simulations"""
    room_polygon: List[List[float]]
    windows: Dict[str, WindowGeometry]
    simulations: Dict[str, Simulation]

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> List['MergerRequest']:
        """Parse dictionary into MergerRequest

        Args:
            content: Dictionary with parameters, simulation, shape, and status from model service
                    Should also include direction_angle dict from orchestration results

        Returns:
            List with single MergerRequest instance
        """
        params = content.get(RequestField.PARAMETERS.value, {})
        room_polygon = params.get(RequestField.ROOM_POLYGON.value, [])
        windows_dict = params.get(RequestField.WINDOWS.value, {})
        direction_angles_dict = content.get(RequestField.DIRECTION_ANGLE.value, {})

        print(direction_angles_dict)

        windows = {}
        for window_name, window_data in windows_dict.items():
            window_geom = WindowGeometry.from_dict(window_data)

            if isinstance(direction_angles_dict, dict) and window_name in direction_angles_dict:
                window_geom.direction_angle = direction_angles_dict[window_name]

            windows[window_name] = window_geom

        # Get per-window simulations dict {window_name: prediction_array}
        simulations_dict = content.get('simulations', {})
        encoder_masks = content.get(RequestField.MASK.value, {})

        simulations = {}
        for window_name in windows.keys():
            window_mask = encoder_masks.get(window_name) if isinstance(encoder_masks, dict) else None
            window_simulation = simulations_dict.get(window_name, [])

            simulations[window_name] = Simulation(
                df_values=np.array(window_simulation) if window_simulation else np.array([]),
                mask=np.array(window_mask) if window_mask is not None else None
            )

        return [cls(
            room_polygon=room_polygon,
            windows=windows,
            simulations=simulations
        )]

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
            if window_geom.direction_angle is None:
                windows_dict[window_name][RequestField.DIRECTION_ANGLE.value] = 0

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
                RequestField.RESULT.value: self._array_to_list(self.df_values),
                RequestField.MASK.value: self._array_to_list(self.mask)
            }
        )

