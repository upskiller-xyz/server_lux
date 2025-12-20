from dataclasses import dataclass
from typing import Optional


@dataclass
class WindowPosition:
    x1: float
    y1: float
    x2: float
    y2: float
    direction_angle: Optional[float] = None


@dataclass
class RoomGeometry:
    room_polygon: list
    windows: dict
