from dataclasses import dataclass
from typing import Dict, Any, List

from .base_contracts import RemoteServiceRequest, StandardResponse
from .domain_models import WindowGeometry
from ....enums import RequestField, ResponseKey


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
