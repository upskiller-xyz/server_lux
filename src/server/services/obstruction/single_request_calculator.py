from typing import Dict, Any, List, Optional
import time
import aiohttp
import asyncio
from ...interfaces import ILogger
from ...enums import ServiceName, EndpointType, RequestField, ResponseKey, ResponseStatus, HTTPHeader, HTTPContentType
from ...exceptions import ServiceConnectionError, ServiceTimeoutError, ServiceResponseError, ServiceAuthorizationError
from .config import WindowGeometry, ObstructionCalculationConfig, ObstructionResult
from .calculator_interface import IObstructionCalculator


class SingleRequestObstructionCalculator(IObstructionCalculator):
    """Calculator that makes ONE request to /obstruction_parallel endpoint

    Uses single HTTP request to calculate all directions simultaneously.
    More efficient than parallel requests for large direction counts.
    Follows Single Responsibility Principle - only handles single-request calculation.
    """

    def __init__(self, logger: ILogger, api_url: str, api_token: Optional[str] = None):
        """Initialize calculator

        Args:
            logger: Logger instance
            api_url: URL of obstruction_parallel endpoint
            api_token: Optional API token for authorization
        """
        self._logger = logger
        self._api_token = api_token
        self._api_url = api_url  # Should be http://51.15.197.220:8081/obstruction_parallel

    def _parse_response_angles(self, result: Dict[str, Any]) -> tuple[List[float], List[float]]:
        """Parse obstruction angles from response using adapter-map pattern

        Handles two response formats:
        1. Flat format: {"horizon_angles": [...], "zenith_angles": [...]}
        2. Nested format: {"data": {"results": [{"horizon": {...}, "zenith": {...}}]}}

        Args:
            result: Response data from obstruction service

        Returns:
            Tuple of (horizon_angles, zenith_angles)
        """
        # Check for flat arrays format (local endpoint)
        if ResponseKey.HORIZON_ANGLES.value in result and ResponseKey.ZENITH_ANGLES.value in result:
            return (
                result.get(ResponseKey.HORIZON_ANGLES.value, []),
                result.get(ResponseKey.ZENITH_ANGLES.value, [])
            )

        # Check for nested results format (remote server)
        if ResponseKey.DATA.value in result and ResponseKey.RESULTS.value in result[ResponseKey.DATA.value]:
            results = result[ResponseKey.DATA.value][ResponseKey.RESULTS.value]
            horizon_angles = [
                r[ResponseKey.HORIZON.value][ResponseKey.OBSTRUCTION_ANGLE_DEGREES.value]
                for r in results
            ]
            zenith_angles = [
                r[ResponseKey.ZENITH.value][ResponseKey.OBSTRUCTION_ANGLE_DEGREES.value]
                for r in results
            ]
            self._logger.info(f"Parsed nested results format with {len(results)} entries")
            return (horizon_angles, zenith_angles)

        # Unknown format
        self._logger.error(f"Unknown response format! Keys: {list(result.keys())}")
        return ([], [])

    async def calculate(
        self,
        window: WindowGeometry,
        mesh: List[List[float]],
        config: ObstructionCalculationConfig
    ) -> List[ObstructionResult]:
        """Calculate obstruction angles using single request to obstruction_parallel endpoint

        Args:
            window: Window geometry
            mesh: Obstruction mesh data
            config: Calculation configuration

        Returns:
            List of obstruction results

        Raises:
            ServiceAuthorizationError: If authorization fails (403)
            ServiceConnectionError: If connection to service fails
            ServiceTimeoutError: If request times out
            ServiceResponseError: If service returns error response
        """
        start_time = time.time()
        self._logger.info(f"Sending single request to {self._api_url} for {config.num_directions} directions")

        # Prepare request payload using RequestField enums
        payload = {
            RequestField.X.value: window.x,
            RequestField.Y.value: window.y,
            RequestField.Z.value: window.z,
            RequestField.DIRECTION_ANGLE.value: window.direction_angle,
            RequestField.MESH.value: mesh
        }

        # Log what we're sending
        self._logger.info(f"📤 Payload to obstruction_parallel:")
        self._logger.info(f"   x={window.x:.2f}, y={window.y:.2f}, z={window.z:.2f}")
        self._logger.info(f"   direction_angle={window.direction_angle:.4f} rad")
        self._logger.info(f"   mesh: {len(mesh)} triangles")
        self._logger.info(f"   Payload size: ~{len(str(payload))} chars")

        # Add Authorization header if token is provided
        headers = {HTTPHeader.CONTENT_TYPE.value: HTTPContentType.JSON.value}
        if self._api_token:
            headers[HTTPHeader.AUTHORIZATION.value] = f"Bearer {self._api_token}"

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
            self._logger.info(f"Response status: {result.get(ResponseKey.STATUS.value)}")

            # Parse the response using ResponseStatus enum
            if result.get(ResponseKey.STATUS.value) == ResponseStatus.SUCCESS.value:
                # Parse angles using helper method
                horizon_angles, zenith_angles = self._parse_response_angles(result)

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
                error_msg = result.get(ResponseKey.ERROR.value, "Unknown error")
                raise Exception(f"Obstruction service error: {error_msg}")

        except aiohttp.ClientResponseError as e:
            # Special handling for 403 Forbidden (authorization errors)
            if e.status == 403:
                error = ServiceAuthorizationError(
                    service_name=ServiceName.OBSTRUCTION.value,
                    endpoint=f"/{EndpointType.OBSTRUCTION_PARALLEL.value}",
                    error_message=e.message
                )
                self._logger.error(error.get_log_message())
                raise error
            else:
                error = ServiceResponseError(
                    service_name=ServiceName.OBSTRUCTION.value,
                    endpoint=f"/{EndpointType.OBSTRUCTION_PARALLEL.value}",
                    status_code=e.status,
                    error_message=e.message
                )
                self._logger.error(error.get_log_message())
                raise error
        except aiohttp.ClientConnectorError as e:
            # Connection failures - cannot connect to host
            error = ServiceConnectionError(
                service_name=ServiceName.OBSTRUCTION.value,
                endpoint=f"/{EndpointType.OBSTRUCTION_PARALLEL.value}",
                address=self._api_url,
                original_error=e
            )
            self._logger.error(error.get_log_message())
            raise error
        except aiohttp.ClientError as e:
            # Other HTTP errors
            error = ServiceConnectionError(
                service_name=ServiceName.OBSTRUCTION.value,
                endpoint=f"/{EndpointType.OBSTRUCTION_PARALLEL.value}",
                address=self._api_url,
                original_error=e
            )
            self._logger.error(error.get_log_message())
            raise error
        except asyncio.TimeoutError as e:
            error = ServiceTimeoutError(
                service_name=ServiceName.OBSTRUCTION.value,
                endpoint=f"/{EndpointType.OBSTRUCTION_PARALLEL.value}",
                timeout_seconds=config.timeout_seconds
            )
            self._logger.error(error.get_log_message())
            raise error
