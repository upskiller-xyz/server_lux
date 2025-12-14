from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import asyncio
import aiohttp
import math
import numpy as np
import time
from abc import ABC, abstractmethod
from ..interfaces import ILogger
from ..enums import ServiceURL
from ..exceptions import ServiceConnectionError, ServiceTimeoutError, ServiceResponseError, ServiceAuthorizationError


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


class SingleRequestObstructionCalculator(IObstructionCalculator):
    """Calculator that makes ONE request to /obstruction_parallel endpoint"""

    def __init__(self, logger: ILogger, api_url: str, api_token: Optional[str] = None):
        self._logger = logger
        self._api_token = api_token
        self._api_url = api_url  # Should be http://51.15.197.220:8081/obstruction_parallel

    async def calculate(self, window: WindowGeometry, mesh: List[List[float]],
                       config: ObstructionCalculationConfig) -> List[ObstructionResult]:
        """Calculate obstruction angles using single request to obstruction_parallel endpoint"""
        start_time = time.time()
        self._logger.info(f"Sending single request to {self._api_url} for {config.num_directions} directions")

        # Prepare request payload
        payload = {
            "x": window.x,
            "y": window.y,
            "z": window.z,
            "direction_angle": window.direction_angle,
            "mesh": mesh
        }

        # Log what we're sending
        self._logger.info(f"📤 Payload to obstruction_parallel:")
        self._logger.info(f"   x={window.x:.2f}, y={window.y:.2f}, z={window.z:.2f}")
        self._logger.info(f"   direction_angle={window.direction_angle:.4f} rad")
        self._logger.info(f"   mesh: {len(mesh)} triangles")
        self._logger.info(f"   Payload size: ~{len(str(payload))} chars")

        # Add Authorization header if token is provided
        headers = {"Content-Type": "application/json"}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"

        try:
            timeout_obj = aiohttp.ClientTimeout(total=config.timeout_seconds)
            async with aiohttp.ClientSession() as session:
                self._logger.info(f"[{time.time():.3f}] → Sending single obstruction_parallel request")
                async with session.post(self._api_url, json=payload, headers=headers, timeout=timeout_obj) as response:
                    response.raise_for_status()
                    result = await response.json()

            request_time = time.time() - start_time
            self._logger.info(f"[{time.time():.3f}] ← Received obstruction_parallel response in {request_time:.2f}s")

            # Log the response structure for debugging
            self._logger.info(f"Response keys: {list(result.keys())}")
            self._logger.info(f"Response status: {result.get('status')}")

            # Parse the response
            if result.get("status") == "success":
                # Check if response has flat arrays (our local endpoint format)
                if "horizon_angles" in result and "zenith_angles" in result:
                    horizon_angles = result.get("horizon_angles", [])
                    zenith_angles = result.get("zenith_angles", [])
                # Or nested results format (remote server format)
                elif "data" in result and "results" in result["data"]:
                    results = result["data"]["results"]
                    horizon_angles = [r["horizon"]["obstruction_angle_degrees"] for r in results]
                    zenith_angles = [r["zenith"]["obstruction_angle_degrees"] for r in results]
                    self._logger.info(f"Parsed nested results format with {len(results)} entries")
                else:
                    self._logger.error(f"Unknown response format! Keys: {list(result.keys())}")
                    horizon_angles = []
                    zenith_angles = []

                self._logger.info(f"Parsed angles - horizon: {len(horizon_angles)}, zenith: {len(zenith_angles)}")
                if len(horizon_angles) == 0 or len(zenith_angles) == 0:
                    self._logger.error(f"Empty angle arrays! Response keys: {list(result.keys())}")

                # Create ObstructionResult objects
                # Note: We don't have individual direction angles from this endpoint
                # So we'll calculate them based on the config
                direction_angles = config.get_direction_angles(window.direction_angle)

                obstruction_results = []
                for i, (direction_angle, horizon_angle, zenith_angle) in enumerate(
                    zip(direction_angles, horizon_angles, zenith_angles)
                ):
                    obstruction_results.append(ObstructionResult(
                        direction_angle=direction_angle,
                        horizon_angle=horizon_angle,
                        zenith_angle=zenith_angle,
                        horizon_highest_point={},  # Not provided by this endpoint
                        zenith_highest_point={}    # Not provided by this endpoint
                    ))

                self._logger.info(f"Completed obstruction calculation in {request_time:.2f}s")
                return obstruction_results
            else:
                error_msg = result.get("error", "Unknown error")
                raise Exception(f"Obstruction service error: {error_msg}")

        except aiohttp.ClientResponseError as e:
            # Special handling for 403 Forbidden (authorization errors)
            if e.status == 403:
                error = ServiceAuthorizationError(
                    service_name="obstruction",
                    endpoint="/obstruction_parallel",
                    error_message=e.message
                )
                self._logger.error(error.get_log_message())
                raise error
            else:
                error = ServiceResponseError(
                    service_name="obstruction",
                    endpoint="/obstruction_parallel",
                    status_code=e.status,
                    error_message=e.message
                )
                self._logger.error(error.get_log_message())
                raise error
        except aiohttp.ClientConnectorError as e:
            # Connection failures - cannot connect to host
            error = ServiceConnectionError(
                service_name="obstruction",
                endpoint="/obstruction_parallel",
                address=self._api_url,
                original_error=e
            )
            self._logger.error(error.get_log_message())
            raise error
        except aiohttp.ClientError as e:
            # Other HTTP errors
            error = ServiceConnectionError(
                service_name="obstruction",
                endpoint="/obstruction_parallel",
                address=self._api_url,
                original_error=e
            )
            self._logger.error(error.get_log_message())
            raise error
        except asyncio.TimeoutError as e:
            error = ServiceTimeoutError(
                service_name="obstruction",
                endpoint="/obstruction_parallel",
                timeout_seconds=config.timeout_seconds
            )
            self._logger.error(error.get_log_message())
            raise error


class ParallelObstructionCalculator(IObstructionCalculator):
    """Calculator that makes parallel requests to obstruction service (64 individual requests)"""

    def __init__(self, logger: ILogger, api_url: str = None, api_token: Optional[str] = None):
        self._logger = logger
        self._api_token = api_token
        # Use dynamic URL resolution from ServiceURL enum
        if api_url is None:
            self._api_url = f"{ServiceURL.OBSTRUCTION.value}/obstruction"
        else:
            self._api_url = api_url

    async def calculate(self, window: WindowGeometry, mesh: List[List[float]],
                       config: ObstructionCalculationConfig) -> List[ObstructionResult]:
        """Calculate obstruction angles for all directions in parallel"""
        start_time = time.time()
        self._logger.info(f"Starting parallel obstruction calculation for {config.num_directions} directions")

        # Get all direction angles
        direction_angles = config.get_direction_angles(window.direction_angle)
        self._logger.info(f"Direction angles range: {math.degrees(direction_angles[0]):.1f}° to {math.degrees(direction_angles[-1]):.1f}°")

        # Create tasks for parallel execution
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._calculate_single_direction(
                    session, window.x, window.y, window.z,
                    direction_angle, mesh, config.timeout_seconds
                )
                for direction_angle in direction_angles
            ]

            self._logger.info(f"Created {len(tasks)} async tasks, submitting all requests in parallel...")
            task_submit_time = time.time()

            # Execute all requests in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            gather_time = time.time() - task_submit_time
            self._logger.info(f"asyncio.gather completed in {gather_time:.2f}s")

        elapsed_requests = time.time() - start_time
        self._logger.info(f"Parallel HTTP requests completed in {elapsed_requests:.2f}s")

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

        total_time = time.time() - start_time
        self._logger.info(f"Completed {len(obstruction_results)} obstruction calculations in {total_time:.2f}s")
        return obstruction_results

    async def _calculate_single_direction(self, session: aiohttp.ClientSession,
                                         x: float, y: float, z: float,
                                         direction_angle: float, mesh: List[List[float]],
                                         timeout: int) -> Dict[str, Any]:
        """Calculate obstruction for a single direction"""
        direction_deg = math.degrees(direction_angle)
        payload = {
            "x": x,
            "y": y,
            "z": z,
            "direction_angle": direction_angle,
            "mesh": mesh,
            # Optimization: Enable early-exit ray casting when no intersection found
            # This checks if a horizontal ray hits anything before doing expensive calculations
            "use_early_exit_optimization": True
        }

        # Add Authorization header if token is provided
        headers = {"Content-Type": "application/json"}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"

        try:
            send_time = time.time()
            self._logger.info(f"[{send_time:.3f}] ↗ SENT request for direction {direction_deg:.1f}°")

            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with session.post(self._api_url, json=payload, headers=headers, timeout=timeout_obj) as response:
                response.raise_for_status()
                result = await response.json()

            receive_time = time.time()
            request_duration = receive_time - send_time
            self._logger.info(f"[{receive_time:.3f}] ↙ COLLECTED response for direction {direction_deg:.1f}° (took {request_duration:.2f}s)")
            return result
        except aiohttp.ClientResponseError as e:
            # Special handling for 403 Forbidden (authorization errors)
            if e.status == 403:
                error = ServiceAuthorizationError(
                    service_name="obstruction",
                    endpoint="/obstruction",
                    error_message=e.message
                )
                self._logger.error(f"{error.get_log_message()} (direction: {direction_deg:.1f}°)")
                raise error
            else:
                error = ServiceResponseError(
                    service_name="obstruction",
                    endpoint="/obstruction",
                    status_code=e.status,
                    error_message=e.message
                )
                self._logger.error(f"{error.get_log_message()} (direction: {direction_deg:.1f}°)")
                raise error
        except aiohttp.ClientConnectorError as e:
            # Connection failures - cannot connect to host
            error = ServiceConnectionError(
                service_name="obstruction",
                endpoint="/obstruction",
                address=self._api_url,
                original_error=e
            )
            self._logger.error(f"{error.get_log_message()} (direction: {direction_deg:.1f}°)")
            raise error
        except aiohttp.ClientError as e:
            # Other HTTP errors
            error = ServiceConnectionError(
                service_name="obstruction",
                endpoint="/obstruction",
                address=self._api_url,
                original_error=e
            )
            self._logger.error(f"{error.get_log_message()} (direction: {direction_deg:.1f}°)")
            raise error
        except asyncio.TimeoutError as e:
            error = ServiceTimeoutError(
                service_name="obstruction",
                endpoint="/obstruction",
                timeout_seconds=timeout
            )
            self._logger.error(f"{error.get_log_message()} (direction: {direction_deg:.1f}°)")
            raise error


class ObstructionCalculationService:
    """Service for calculating obstruction angles across multiple directions"""

    def __init__(self, calculator: IObstructionCalculator, logger: ILogger):
        self._calculator = calculator
        self._logger = logger

    def calculate_multi_direction(self, x: float, y: float, z: float,
                                  direction_angle: float | None, mesh: List[List[float]],
                                  start_angle: float = 17.5, end_angle: float = 162.5,
                                  num_directions: int = 64) -> Dict[str, Any]:
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
