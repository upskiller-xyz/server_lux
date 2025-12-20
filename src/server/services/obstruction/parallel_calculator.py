import logging
from typing import Dict, Any, List, Optional
import time
import math
import aiohttp
import asyncio
from ...enums import EndpointType, RequestField, ResponseKey, ServiceName, HTTPHeader, HTTPContentType
from ...exceptions import ServiceConnectionError, ServiceTimeoutError, ServiceResponseError, ServiceAuthorizationError
from .config import WindowGeometry, ObstructionCalculationConfig, ObstructionResult
from .calculator_interface import IObstructionCalculator


class ParallelObstructionCalculator(IObstructionCalculator):

    def __init__(self, api_url: str = None, api_token: Optional[str] = None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._api_token = api_token
        self._api_url = api_url

    async def calculate(
        self,
        window: WindowGeometry,
        mesh: List[List[float]],
        config: ObstructionCalculationConfig
    ) -> List[ObstructionResult]:
        start_time = time.time()
        direction_angles = config.get_direction_angles(window.direction_angle)

        async with aiohttp.ClientSession() as session:
            tasks = [
                self._calculate_single_direction(
                    session, window.x, window.y, window.z,
                    direction_angle, mesh, config.timeout_seconds
                )
                for direction_angle in direction_angles
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

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
        self._logger.info(f"Completed {len(obstruction_results)} calculations in {total_time:.2f}s")
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
        direction_deg = math.degrees(direction_angle)
        payload = {
            RequestField.X.value: x,
            RequestField.Y.value: y,
            RequestField.Z.value: z,
            RequestField.DIRECTION_ANGLE.value: direction_angle,
            RequestField.MESH.value: mesh,
            RequestField.USE_EARLY_EXIT_OPTIMIZATION.value: True
        }

        headers = {HTTPHeader.CONTENT_TYPE.value: HTTPContentType.JSON.value}
        if self._api_token:
            headers[HTTPHeader.AUTHORIZATION.value] = f"Bearer {self._api_token}"

        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with session.post(self._api_url, json=payload, headers=headers, timeout=timeout_obj) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientResponseError as e:
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
            error = ServiceConnectionError(
                service_name=ServiceName.OBSTRUCTION.value,
                endpoint=f"/{EndpointType.OBSTRUCTION.value}",
                address=self._api_url,
                original_error=e
            )
            self._logger.error(f"{error.get_log_message()} (direction: {direction_deg:.1f}°)")
            raise error
        except aiohttp.ClientError as e:
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
