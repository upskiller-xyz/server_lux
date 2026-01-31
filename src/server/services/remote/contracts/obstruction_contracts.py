from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import logging

from .base_contracts import RemoteServiceRequest, RemoteServiceResponse
from ....enums import RequestField, ResponseKey

logger = logging.getLogger('logger')


@dataclass
class ObstructionRequest(RemoteServiceRequest):
    """Request for obstruction angle calculations (single point and direction)

    Used for /horizon, /zenith, and /obstruction endpoints.
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
                x=content.get(RequestField.X.value, 0.0),
                y=content.get(RequestField.Y.value, 0.0),
                z=content.get(RequestField.Z.value, 0.0),
                direction_angle=content.get(RequestField.DIRECTION_ANGLE.value, 0.0),
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
class ObstructionResponse(RemoteServiceResponse):
    """Response from obstruction calculations

    Used for /obstruction_parallel endpoint.
    Parses the standardized data.results format from the obstruction microservice.
    """
    status: Optional[str] = None
    horizon: Optional[List[float]] = None
    zenith: Optional[List[float]] = None

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> 'ObstructionResponse':
        """Parse response data from obstruction service

        Expects the standardized data.results format from /obstruction_parallel.
        Each result contains horizon/zenith with obstruction_angle_degrees.
        """
        data = content.get(ResponseKey.DATA.value, {})
        results = data.get(ResponseKey.RESULTS.value, [])
        status = content.get(ResponseKey.STATUS.value, 'success')

        horizon = [
            r.get(ResponseKey.HORIZON.value, {}).get(ResponseKey.OBSTRUCTION_ANGLE_DEGREES.value, 0.0)
            for r in results
        ]
        zenith = [
            r.get(ResponseKey.ZENITH.value, {}).get(ResponseKey.OBSTRUCTION_ANGLE_DEGREES.value, 0.0)
            for r in results
        ]

        return cls(
            status=status,
            horizon=horizon,
            zenith=zenith
        )
    
    @property
    def is_success(self) -> bool:
        """Check if response indicates success"""
        return self.status == ResponseKey.SUCCESS.value
    
    @property
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        result = {}
        if self.horizon is not None:
            result[ResponseKey.HORIZON.value] = self.horizon
        if self.zenith is not None:
            result[ResponseKey.ZENITH.value] = self.zenith
        return result


