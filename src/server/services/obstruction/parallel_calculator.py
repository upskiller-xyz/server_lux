from typing import Dict, Any, List, Optional
import time
import math
import aiohttp
import asyncio
from ...interfaces import ILogger
from ...enums import ServiceURL, EndpointType, RequestField, ResponseKey, ServiceName, HTTPHeader, HTTPContentType
from ...exceptions import ServiceConnectionError, ServiceTimeoutError, ServiceResponseError, ServiceAuthorizationError
from .config import WindowGeometry, ObstructionCalculationConfig, ObstructionResult
from .calculator_interface import IObstructionCalculator


class ParallelObstructionCalculator(IObstructionCalculator):
    """Calculator that makes parallel requests to obstruction service (64 individual requests)

    Uses asyncio to send multiple HTTP requests simultaneously.
    Each direction calculated independently in parallel.
    Follows Single Responsibility Principle - only handles parallel calculation.
    """

    def __init__(self, logger: ILogger, api_url: str = None, api_token: Optional[str] = None):
        """Initialize calculator

        Args:
            logger: Logger instance
            api_url: URL of obstruction endpoint (optional, uses ServiceURL.OBSTRUCTION if not provided)
            api_token: Optional API token for authorization
        """
        self._logger = logger
        self._api_token = api_token
        # Use dynamic URL resolution from ServiceURL enum
        if api_url is None:
            self._api_url = f"{ServiceURL.OBSTRUCTION.value}/{EndpointType.OBSTRUCTION.value}"
        else:
            self._api_url = api_url

    async def calculate(
        self,
        window: WindowGeometry,
        mesh: List[List[float]],
        config: ObstructionCalculationConfig
    ) -> List[ObstructionResult]:
        """Calculate obstruction angles for all directions in parallel

        Args:
            window: Window geometry
            mesh: Obstruction mesh data
            config: Calculation configuration

        Returns:
            List of obstruction results

        Raises:
            ServiceAuthorizationError: If any request fails authorization
            ServiceConnectionError: If connection to service fails
            ServiceTimeoutError: If any request times out
            ServiceResponseError: If service returns error response
        """
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

            data = result[ResponseKey.DATA.value]
            obstruction_results.append(ObstructionResult(
                direction_angle=direction_angle,
                horizon_angle=data[ResponseKey.HORIZON.value][ResponseKey.OBSTRUCTION_ANGLE_DEGREES.value],
                zenith_angle=data[ResponseKey.ZENITH.value][ResponseKey.OBSTRUCTION_ANGLE_DEGREES.value],
                horizon_highest_point=data[ResponseKey.HORIZON.value][ResponseKey.HIGHEST_POINT.value],
                zenith_highest_point=data[ResponseKey.ZENITH.value][ResponseKey.HIGHEST_POINT.value]
            ))

        total_time = time.time() - start_time
        self._logger.info(f"Completed {len(obstruction_results)} obstruction calculations in {total_time:.2f}s")
        return obstruction_results

    async def _calculate_single_direction(
        self,
        session: aiohttp.ClientSession,
        x: float,
        y: float,
        z: float,
        direction_angle: float,
        mesh: List[List[float]],
        timeout: int
    ) -> Dict[str, Any]:
        """Calculate obstruction for a single direction

        Args:
            session: aiohttp session for making requests
            x, y, z: Window position
            direction_angle: Direction angle in radians
            mesh: Obstruction mesh
            timeout: Timeout in seconds

        Returns:
            Response from obstruction service

        Raises:
            ServiceAuthorizationError: If authorization fails (403)
            ServiceConnectionError: If connection fails
            ServiceTimeoutError: If request times out
            ServiceResponseError: If service returns error
        """
        direction_deg = math.degrees(direction_angle)
        payload = {
            RequestField.X.value: x,
            RequestField.Y.value: y,
            RequestField.Z.value: z,
            RequestField.DIRECTION_ANGLE.value: direction_angle,
            RequestField.MESH.value: mesh,
            # Optimization: Enable early-exit ray casting when no intersection found
            # This checks if a horizontal ray hits anything before doing expensive calculations
            RequestField.USE_EARLY_EXIT_OPTIMIZATION.value: True
        }

        # Add Authorization header if token is provided
        headers = {HTTPHeader.CONTENT_TYPE.value: HTTPContentType.JSON.value}
        if self._api_token:
            headers[HTTPHeader.AUTHORIZATION.value] = f"Bearer {self._api_token}"

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
                    service_name=ServiceName.OBSTRUCTION.value,
                    endpoint=f"/{EndpointType.OBSTRUCTION.value}",
                    error_message=e.message
                )
                self._logger.error(f"{error.get_log_message()} (direction: {direction_deg:.1f}°)")
                raise error
            else:
                error = ServiceResponseError(
                    service_name=ServiceName.OBSTRUCTION.value,
                    endpoint=f"/{EndpointType.OBSTRUCTION.value}",
                    status_code=e.status,
                    error_message=e.message
                )
                self._logger.error(f"{error.get_log_message()} (direction: {direction_deg:.1f}°)")
                raise error
        except aiohttp.ClientConnectorError as e:
            # Connection failures - cannot connect to host
            error = ServiceConnectionError(
                service_name=ServiceName.OBSTRUCTION.value,
                endpoint=f"/{EndpointType.OBSTRUCTION.value}",
                address=self._api_url,
                original_error=e
            )
            self._logger.error(f"{error.get_log_message()} (direction: {direction_deg:.1f}°)")
            raise error
        except aiohttp.ClientError as e:
            # Other HTTP errors
            error = ServiceConnectionError(
                service_name=ServiceName.OBSTRUCTION.value,
                endpoint=f"/{EndpointType.OBSTRUCTION.value}",
                address=self._api_url,
                original_error=e
            )
            self._logger.error(f"{error.get_log_message()} (direction: {direction_deg:.1f}°)")
            raise error
        except asyncio.TimeoutError as e:
            error = ServiceTimeoutError(
                service_name=ServiceName.OBSTRUCTION.value,
                endpoint=f"/{EndpointType.OBSTRUCTION.value}",
                timeout_seconds=timeout
            )
            self._logger.error(f"{error.get_log_message()} (direction: {direction_deg:.1f}°)")
            raise error
