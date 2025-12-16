from typing import Dict, Any, List
import asyncio
import time
import math
from ...interfaces import ILogger
from ...enums import RequestField, ResponseKey, ResponseStatus
from ...constants import ObstructionAngleDefaults
from .config import ObstructionCalculationConfig, WindowGeometry
from .calculator_interface import IObstructionCalculator


class ObstructionCalculationService:
    """Service for calculating obstruction angles across multiple directions

    Orchestrates obstruction calculation using Strategy pattern.
    Delegates actual calculation to IObstructionCalculator implementation.
    Follows Single Responsibility Principle - only coordinates calculation workflow.
    """

    def __init__(self, calculator: IObstructionCalculator, logger: ILogger):
        """Initialize service

        Args:
            calculator: Calculator implementation (single-request or parallel)
            logger: Logger instance
        """
        self._calculator = calculator
        self._logger = logger

    def calculate_multi_direction(
        self,
        x: float,
        y: float,
        z: float,
        direction_angle: float | None,
        mesh: List[List[float]],
        start_angle: float = ObstructionAngleDefaults.START_ANGLE_DEGREES,
        end_angle: float = ObstructionAngleDefaults.END_ANGLE_DEGREES,
        num_directions: int = ObstructionAngleDefaults.NUM_DIRECTIONS
    ) -> Dict[str, Any]:
        """
        Calculate obstruction angles for multiple directions around a window

        Args:
            x, y, z: Window center coordinates
            direction_angle: Window's facing direction in radians (window normal)
            mesh: Geometry mesh data
            start_angle: Starting angle in half-circle coordinate system where 90° = direction_angle (default 17.5)
            end_angle: Ending angle in half-circle coordinate system where 90° = direction_angle (default 162.5)
            num_directions: Number of directions to calculate (default 64)

        Returns:
            Dictionary with status and stacked obstruction data

        Note:
            The half-circle coordinate system is defined as:
            - 0° = 90° counter-clockwise from window normal
            - 90° = window normal (direction_angle parameter)
            - 180° = 90° clockwise from window normal
        """
        overall_start = time.time()
        self._logger.info(f"Calculating obstruction for window at ({x}, {y}, {z}), "
                         f"direction: {direction_angle} rad")
        self._logger.info(f"Mesh size: {len(mesh)} triangles")

        try:
            # Create configuration
            config_start = time.time()
            config = ObstructionCalculationConfig(
                start_angle_degrees=start_angle,
                end_angle_degrees=end_angle,
                num_directions=num_directions
            )
            self._logger.info(f"⏱️  Config creation: {time.time() - config_start:.3f}s")

            # Create window geometry
            window = WindowGeometry(x=x, y=y, z=z, direction_angle=direction_angle)

            # Run async calculation
            loop_start = time.time()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._logger.info(f"⏱️  Event loop creation: {time.time() - loop_start:.3f}s")

            try:
                calc_start = time.time()
                results = loop.run_until_complete(
                    self._calculator.calculate(window, mesh, config)
                )
                self._logger.info(f"⏱️  Async calculation: {time.time() - calc_start:.3f}s")
            finally:
                loop.close()

            # Stack results in order
            stack_start = time.time()
            horizon_angles = [r.horizon_angle for r in results]
            zenith_angles = [r.zenith_angle for r in results]
            self._logger.info(f"⏱️  Result stacking: {time.time() - stack_start:.3f}s")
            direction_angles_degrees = [math.degrees(r.direction_angle) for r in results]

            return {
                ResponseKey.STATUS.value: ResponseStatus.SUCCESS.value,
                ResponseKey.DATA.value: {
                    ResponseKey.HORIZON_ANGLES.value: horizon_angles,
                    ResponseKey.ZENITH_ANGLES.value: zenith_angles,
                    ResponseKey.DIRECTION_ANGLE.value: direction_angles_degrees,
                    RequestField.NUM_DIRECTIONS.value: len(results),
                    RequestField.START_ANGLE.value: start_angle,
                    RequestField.END_ANGLE.value: end_angle
                }
            }

        except Exception as e:
            self._logger.error(f"Obstruction calculation failed: {str(e)}")
            return {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: f"Obstruction calculation failed: {str(e)}"
            }
