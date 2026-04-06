from dataclasses import dataclass
from typing import Dict, Any, List

from .base_contracts import RemoteServiceRequest, StandardResponse
from .domain_models import WindowGeometry
from ....enums import RequestField


@dataclass
class ExternalReferencePointRequest(RemoteServiceRequest):
    """Request for external reference point calculation

    Used for /get-external-reference-point endpoint to calculate external reference points
    for windows in a room based on room polygon and window positions.
    
    The external reference point is on the opposite edge of the window rectangle
    from the edge that lies on the room polygon (i.e., the external face of the window).
    """
    room_polygon: List[List[float]]
    windows: Dict[str, WindowGeometry]

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> List['ExternalReferencePointRequest']:
        """Parse dictionary into list of ExternalReferencePointRequest (one per window)

        Args:
            content: Dictionary with 'room_polygon' and 'windows' keys,
                    or with 'parameters' key containing room_polygon and windows

        Returns:
            List of ExternalReferencePointRequest instances (one per window)
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
class ExternalReferencePointResponse(StandardResponse):
    """Response from external reference point calculation

    Returns the external reference point coordinates for each window.
    This is the point on the opposite edge of the window from the polygon edge.

    Expected format:
    {
        "external_reference_point": {
            "window_id": {"x": 0.0, "y": 0.0, "z": 1.75}
        }
    }
    """
    external_reference_point: Dict[str, Dict[str, float]]

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> 'ExternalReferencePointResponse':
        """Parse response and return external reference points"""
        external_reference_point = content.get(RequestField.EXTERNAL_REFERENCE_POINT.value, {})
        return cls(external_reference_point)

    @property
    def to_dict(self) -> Dict[str, Any]:
        return {
            RequestField.EXTERNAL_REFERENCE_POINT.value: self.external_reference_point,
            RequestField.REFERENCE_POINT.value: self.external_reference_point
        }
