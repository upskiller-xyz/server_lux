from typing import Dict, Any, List
from dataclasses import dataclass
import asyncio
import aiohttp
import math
import numpy as np
from abc import ABC, abstractmethod
from ..interfaces import ILogger
from ..enums import ServiceURL


@dataclass
class ObstructionCalculationConfig:
    """Configuration for obstruction angle calculations"""
    start_angle_degrees: float = 17.5
    end_angle_degrees: float = 162.5
    num_directions: int = 64
    timeout_seconds: int = 300

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
    """Window geometry parameters"""
    x: float
    y: float
    z: float
    direction_angle: float  # Radians, 0 = +X (East), π/2 = +Y (North), etc.


@dataclass
class ObstructionResult:
    """Result from a single obstruction calculation"""
    direction_angle: float
    horizon_angle: float
    zenith_angle: float
    horizon_highest_point: Dict[str, float]
    zenith_highest_point: Dict[str, float]


class IObstructionCalculator(ABC):
    """Interface for obstruction calculation strategies"""

    @abstractmethod
    async def calculate(self, window: WindowGeometry, mesh: List[List[float]],
                       config: ObstructionCalculationConfig) -> List[ObstructionResult]:
        """Calculate obstruction angles for all directions"""
        pass


class ParallelObstructionCalculator(IObstructionCalculator):
    """Calculator that makes parallel requests to obstruction service"""

    def __init__(self, logger: ILogger, api_url: str = None):
        self._logger = logger
        # Use dynamic URL resolution from ServiceURL enum
        if api_url is None:
            self._api_url = f"{ServiceURL.OBSTRUCTION.value}/obstruction"
        else:
            self._api_url = api_url

    async def calculate(self, window: WindowGeometry, mesh: List[List[float]],
                       config: ObstructionCalculationConfig) -> List[ObstructionResult]:
        """Calculate obstruction angles for all directions in parallel"""
        self._logger.info(f"Starting parallel obstruction calculation for {config.num_directions} directions")

        # Get all direction angles
        direction_angles = config.get_direction_angles(window.direction_angle)

        # Create tasks for parallel execution
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._calculate_single_direction(
                    session, window.x, window.y, window.z,
                    direction_angle, mesh, config.timeout_seconds
                )
                for direction_angle in direction_angles
            ]

            # Execute all requests in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        obstruction_results = []
        for i, (direction_angle, result) in enumerate(zip(direction_angles, results)):
            if isinstance(result, Exception):
                self._logger.error(f"Failed to calculate obstruction for direction {i}: {str(result)}")
                raise result

            obstruction_results.append(ObstructionResult(
                direction_angle=direction_angle,
                horizon_angle=result['data']['horizon']['obstruction_angle_degrees'],
                zenith_angle=result['data']['zenith']['obstruction_angle_degrees'],
                horizon_highest_point=result['data']['horizon']['highest_point'],
                zenith_highest_point=result['data']['zenith']['highest_point']
            ))

        self._logger.info(f"Completed {len(obstruction_results)} obstruction calculations")
        return obstruction_results

    async def _calculate_single_direction(self, session: aiohttp.ClientSession,
                                         x: float, y: float, z: float,
                                         direction_angle: float, mesh: List[List[float]],
                                         timeout: int) -> Dict[str, Any]:
        """Calculate obstruction for a single direction"""
        payload = {
            "x": x,
            "y": y,
            "z": z,
            "direction_angle": direction_angle,
            "mesh": mesh
        }

        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with session.post(self._api_url, json=payload, timeout=timeout_obj) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            self._logger.error(f"HTTP error for direction {direction_angle}: {str(e)}")
            raise
        except asyncio.TimeoutError as e:
            self._logger.error(f"Timeout for direction {direction_angle}")
            raise


class ObstructionCalculationService:
    """Service for calculating obstruction angles across multiple directions"""

    def __init__(self, calculator: IObstructionCalculator, logger: ILogger):
        self._calculator = calculator
        self._logger = logger

    def calculate_multi_direction(self, x: float, y: float, z: float,
                                  direction_angle: float, mesh: List[List[float]],
                                  start_angle: float = 17.5, end_angle: float = 162.5,
                                  num_directions: int = 64) -> Dict[str, Any]:
        """
        Calculate obstruction angles for multiple directions around a window

        Args:
            x, y, z: Window center coordinates
            direction_angle: Window's facing direction in radians
            mesh: Geometry mesh data
            start_angle: Starting angle offset in degrees (default 17.5)
            end_angle: Ending angle offset in degrees (default 162.5)
            num_directions: Number of directions to calculate (default 64)

        Returns:
            Dictionary with status and stacked obstruction data
        """
        self._logger.info(f"Calculating obstruction for window at ({x}, {y}, {z}), "
                         f"direction: {direction_angle} rad")

        try:
            # Create configuration
            config = ObstructionCalculationConfig(
                start_angle_degrees=start_angle,
                end_angle_degrees=end_angle,
                num_directions=num_directions
            )

            # Create window geometry
            window = WindowGeometry(x=x, y=y, z=z, direction_angle=direction_angle)

            # Run async calculation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    self._calculator.calculate(window, mesh, config)
                )
            finally:
                loop.close()

            # Stack results in order
            horizon_angles = [r.horizon_angle for r in results]
            zenith_angles = [r.zenith_angle for r in results]
            direction_angles_degrees = [math.degrees(r.direction_angle) for r in results]

            return {
                "status": "success",
                "data": {
                    "horizon_angles": horizon_angles,
                    "zenith_angles": zenith_angles,
                    "direction_angles": direction_angles_degrees,
                    "num_directions": len(results),
                    "start_angle": start_angle,
                    "end_angle": end_angle
                }
            }

        except Exception as e:
            self._logger.error(f"Obstruction calculation failed: {str(e)}")
            return {
                "status": "error",
                "error": f"Obstruction calculation failed: {str(e)}"
            }
