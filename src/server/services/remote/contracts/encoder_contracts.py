from dataclasses import dataclass
from typing import Dict, Any, List
import numpy as np
import io

from .base_contracts import RemoteServiceRequest, StandardResponse
from .domain_models import WindowGeometry, RoomPolygon
from ....enums import RequestField, NPZKey


@dataclass
class Parameters(RemoteServiceRequest):
    """Request for encoder service operations

    Shared parameter structure for room/window configuration.
    """
    window: WindowGeometry
    room: RoomPolygon
    height_roof_over_floor: float = 0
    floor_height_above_terrain: float = 0
    simulation: Any = None
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
    def parse(cls, content: Dict[str, Any]) -> List['Parameters']:

        room_points = content.get(RequestField.ROOM_POLYGON.value, [])
        room = RoomPolygon(points=room_points)
        windows = content.get(RequestField.WINDOWS.value, {})

        # Get obstruction angles and other computed values from orchestration
        obstruction_horizon_raw = content.get(RequestField.OBSTRUCTION_ANGLE_HORIZON.value, {})
        obstruction_zenith_raw = content.get(RequestField.OBSTRUCTION_ANGLE_ZENITH.value, {})
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
    def _parse_window_dict(cls, windows: dict[Any:Any], obstruction_horizon_raw={}, obstruction_zenith_raw={}, direction_angles_raw={}) -> list[tuple[str, WindowGeometry]]:
        wws = []
        obstruction_horizon = cls._normalize_to_dict(obstruction_horizon_raw)
        obstruction_zenith = cls._normalize_to_dict(obstruction_zenith_raw)
        direction_angles_dict = cls._normalize_to_dict(direction_angles_raw)

        for name, w in windows.items():
            window_geom = WindowGeometry.from_dict(w)
            if name in obstruction_horizon:
                window_geom.obstruction_angle_horizon = obstruction_horizon[name]
            if name in obstruction_zenith:
                window_geom.obstruction_angle_zenith = obstruction_zenith[name]
            if name in direction_angles_dict:
                window_geom.direction_angle = direction_angles_dict[name]
            wws.append((name, window_geom))
        return wws

    @classmethod
    def _parse_window_list(cls, windows: list[dict[Any:Any]]) -> list[tuple[str, WindowGeometry]]:
        return [(f"window_{i}", WindowGeometry.from_dict(w)) for i, w in enumerate(windows)]

    @classmethod
    def _normalize_to_dict(cls, field):
        return field if isinstance(field, dict) else {}


@dataclass
class EncoderResponse(StandardResponse):
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
