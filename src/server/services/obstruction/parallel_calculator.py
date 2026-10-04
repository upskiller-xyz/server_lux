import asyncio
import logging
import math
import time
from typing import Any, Dict, List, Optional

import aiohttp

from ...constants import AuthHeaderBuilder, EndpointPathBuilder, ObstructionLogTemplate
from ...enums import (
    EndpointType,
    HTTPContentType,
    HTTPHeader,
    RequestField,
    ResponseKey,
    ServiceName,
)
from ...exceptions import (
    ServiceAuthorizationError,
    ServiceConnectionError,
    ServiceResponseError,
    ServiceTimeoutError,
)
from .calculator_interface import IObstructionCalculator
from .config import ObstructionCalculationConfig, ObstructionResult, WindowGeometry


class ParallelObstructionCalculator(IObstructionCalculator):

    def __init__(self, api_url: str = "", api_token: Optional[str] = ""):
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
                self._logger.error(
                    ObstructionLogTemplate.DIRECTION_FAILED.format(index=i, error=result)
                )
                raise result

            data = result[ResponseKey.DATA.value]
            obstruction_results.append(ObstructionResult(
                direction=direction_angle,
                horizon=data[ResponseKey.HORIZON.value][ResponseKey.OBSTRUCTION_ANGLE_DEGREES.value],
                zenith=data[ResponseKey.ZENITH.value][ResponseKey.OBSTRUCTION_ANGLE_DEGREES.value],
                horizon_highest_point=data[ResponseKey.HORIZON.value][ResponseKey.HIGHEST_POINT.value],
                zenith_highest_point=data[ResponseKey.ZENITH.value][ResponseKey.HIGHEST_POINT.value]
            ))

        total_time = time.time() - start_time
        self._logger.info(
            ObstructionLogTemplate.PARALLEL_COMPLETED.format(
                count=len(obstruction_results), seconds=total_time
            )
        )
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
            headers[HTTPHeader.AUTHORIZATION.value] = AuthHeaderBuilder.bearer(self._api_token)

        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with session.post(self._api_url, json=payload, headers=headers, timeout=timeout_obj) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientResponseError as e:
            if e.status == 403:
                error = ServiceAuthorizationError(
                    service_name=ServiceName.OBSTRUCTION.value,
                    endpoint=EndpointPathBuilder.path(EndpointType.OBSTRUCTION.value),
                    error_message=e.message
                )
                self._logger.error(
                    ObstructionLogTemplate.DIRECTION_ERROR.format(
                        message=error.get_log_message(), direction=direction_deg
                    )
                )
                raise error
            else:
                error = ServiceResponseError(
                    service_name=ServiceName.OBSTRUCTION.value,
                    endpoint=EndpointPathBuilder.path(EndpointType.OBSTRUCTION.value),
                    status_code=e.status,
                    error_message=e.message
                )
                self._logger.error(
                    ObstructionLogTemplate.DIRECTION_ERROR.format(
                        message=error.get_log_message(), direction=direction_deg
                    )
                )
                raise error
        except aiohttp.ClientConnectorError as e:
            error = ServiceConnectionError(
                service_name=ServiceName.OBSTRUCTION.value,
                endpoint=EndpointPathBuilder.path(EndpointType.OBSTRUCTION.value),
                address=self._api_url,
                original_error=e
            )
            self._logger.error(
                    ObstructionLogTemplate.DIRECTION_ERROR.format(
                        message=error.get_log_message(), direction=direction_deg
                    )
                )
            raise error
        except aiohttp.ClientError as e:
            error = ServiceConnectionError(
                service_name=ServiceName.OBSTRUCTION.value,
                endpoint=EndpointPathBuilder.path(EndpointType.OBSTRUCTION.value),
                address=self._api_url,
                original_error=e
            )
            self._logger.error(
                    ObstructionLogTemplate.DIRECTION_ERROR.format(
                        message=error.get_log_message(), direction=direction_deg
                    )
                )
            raise error
        except asyncio.TimeoutError:
            error = ServiceTimeoutError(
                service_name=ServiceName.OBSTRUCTION.value,
                endpoint=EndpointPathBuilder.path(EndpointType.OBSTRUCTION.value),
                timeout_seconds=timeout
            )
            self._logger.error(
                    ObstructionLogTemplate.DIRECTION_ERROR.format(
                        message=error.get_log_message(), direction=direction_deg
                    )
                )
            raise error
