import math
from dataclasses import dataclass
from typing import Optional
from ...interfaces import ILogger
from ...enums import RequestField, ResponseKey


@dataclass
class WindowPosition:
    """Window position interface for direction angle calculation"""
    x1: float
    y1: float
    x2: float
    y2: float
    direction_angle: Optional[float] = None


@dataclass
class RoomGeometry:
    """Room geometry interface for direction angle calculation"""
    room_polygon: list
    windows: dict  # window_name -> WindowPosition


class DirectionAngleResolver:
    """Resolves direction angle using Strategy pattern with priority order

    Priority:
    1. window.direction_angle (if provided)
    2. Calculate from encoder service

    Follows Single Responsibility Principle - only resolves direction angles.
    Uses interface-based parameters instead of Dict[str, Any].
    """

    @staticmethod
    def resolve(
        window_name: str,
        window: WindowPosition,
        room_geometry: RoomGeometry,
        encoder_service: Any,
        logger: ILogger
    ) -> Optional[float]:
        """Resolve direction angle using adapter-map pattern

        Args:
            window_name: Name of the window
            window: Window position data
            room_geometry: Room geometry data
            encoder_service: Encoder service for calculating angles
            logger: Logger instance

        Returns:
            Direction angle in radians, or None if resolution failed
        """
        # Priority 1: Check window.direction_angle
        if window.direction_angle is not None:
            logger.info(f"[{window_name}] Using direction_angle from window: {window.direction_angle:.4f} rad ({math.degrees(window.direction_angle):.2f}°)")
            return window.direction_angle

        # Priority 2: Calculate from encoder service
        logger.info(f"[{window_name}] direction_angle not provided, calling encoder service to calculate it")
        calc_params = {
            RequestField.ROOM_POLYGON.value: room_geometry.room_polygon,
            RequestField.WINDOWS.value: {
                window_name: {
                    RequestField.X1.value: window.x1,
                    RequestField.Y1.value: window.y1,
                    RequestField.X2.value: window.x2,
                    RequestField.Y2.value: window.y2
                }
            }
        }
        direction_result = encoder_service.calculate_direction_angles(calc_params)
        direction_angle = direction_result.get(ResponseKey.DIRECTION_ANGLES.value, {}).get(window_name)

        if direction_angle is not None:
            logger.info(f"[{window_name}] Calculated direction_angle from encoder service: {direction_angle:.4f} rad ({math.degrees(direction_angle):.2f}°)")
        else:
            logger.error(f"[{window_name}] Failed to calculate direction_angle from encoder service")

        return direction_angle
