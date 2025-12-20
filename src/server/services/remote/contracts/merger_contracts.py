from dataclasses import dataclass
from typing import Dict, Any, List
import numpy as np

from .base_contracts import RemoteServiceRequest, StandardResponse
from .domain_models import WindowGeometry, Simulation
from ....enums import RequestField, ResponseKey


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
