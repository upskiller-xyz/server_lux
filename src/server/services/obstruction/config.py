from dataclasses import dataclass
from typing import List
import math
import numpy as np
from ...constants import ObstructionAngleDefaults


@dataclass
class ObstructionCalculationConfig:
    """Configuration for obstruction angle calculations

    Follows dataclass pattern for configuration management.
    Encapsulates calculation parameters and geometry transformation logic.
    """
    start_angle_degrees: float = ObstructionAngleDefaults.START_ANGLE_DEGREES
    end_angle_degrees: float = ObstructionAngleDefaults.END_ANGLE_DEGREES
    num_directions: int = ObstructionAngleDefaults.NUM_DIRECTIONS
    timeout_seconds: int = ObstructionAngleDefaults.TIMEOUT_SECONDS

    def get_direction_angles(self, base_direction: float) -> List[float]:
        """
        Calculate all direction angles relative to the window's base direction

        In a half-circle coordinate system:
        - 0° is 90° counter-clockwise from window normal (left edge of wall)
        - 90° is the window normal direction
        - 180° is 90° clockwise from window normal (right edge of wall)

        We want angles from start_angle_degrees to end_angle_degrees in this system.

        Args:
            base_direction: Window's direction angle in radians (window normal)

        Returns:
            List of absolute direction angles in radians
        """
        # Convert start and end angles from half-circle system to radians
        start_rad = math.radians(self.start_angle_degrees)
        end_rad = math.radians(self.end_angle_degrees)

        # Generate evenly spaced angles in the half-circle coordinate system
        half_circle_angles = np.linspace(start_rad, end_rad, self.num_directions)

        # Convert to absolute directions
        # In half-circle system: 0° = base_direction - π/2, 90° = base_direction, 180° = base_direction + π/2
        # So: absolute_direction = base_direction - π/2 + half_circle_angle
        absolute_angles = [(base_direction - math.pi / 2 + angle) % (2 * math.pi)
                          for angle in half_circle_angles]

        return absolute_angles


@dataclass
class WindowGeometry:
    """Window geometry parameters

    Simple data container for window position and orientation.
    """
    x: float
    y: float
    z: float
    direction_angle: float  # Radians, 0 = +X (East), π/2 = +Y (North), etc.


@dataclass
class ObstructionResult:
    """Result from a single obstruction calculation

    Contains all data from one obstruction angle calculation.
    """
    direction: float
    horizon: float
    zenith: float
    horizon_highest_point: dict
    zenith_highest_point: dict
