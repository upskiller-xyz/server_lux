import asyncio
import logging
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
    ResponseStatus,
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


class SingleRequestObstructionCalculator(IObstructionCalculator):

    def __init__(self, api_url: str, api_token: Optional[str] = None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._api_token = api_token
        self._api_url = api_url

    def _parse_response_angles(self, result: Dict[str, Any]) -> tuple[List[float], List[float]]:
        if ResponseKey.HORIZON.value in result and ResponseKey.ZENITH.value in result:
            return (
                result.get(ResponseKey.HORIZON.value, []),
                result.get(ResponseKey.ZENITH.value, [])
            )

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
            return (horizon_angles, zenith_angles)

        self._logger.error(
            ObstructionLogTemplate.UNKNOWN_FORMAT.format(keys=list(result.keys()))
        )
        return ([], [])

    async def calculate(
        self,
        window: WindowGeometry,
        mesh: List[List[float]],
        config: ObstructionCalculationConfig
    ) -> List[ObstructionResult]:
        start_time = time.time()

        payload = {
            RequestField.X.value: window.x,
            RequestField.Y.value: window.y,
            RequestField.Z.value: window.z,
            RequestField.DIRECTION_ANGLE.value: window.direction_angle,
            RequestField.MESH.value: mesh
        }

        headers = {HTTPHeader.CONTENT_TYPE.value: HTTPContentType.JSON.value}
        if self._api_token:
            headers[HTTPHeader.AUTHORIZATION.value] = AuthHeaderBuilder.bearer(self._api_token)

        try:
            timeout_obj = aiohttp.ClientTimeout(total=config.timeout_seconds)
            async with aiohttp.ClientSession() as session:
                async with session.post(self._api_url, json=payload, headers=headers, timeout=timeout_obj) as response:
                    response.raise_for_status()
                    result = await response.json()

            request_time = time.time() - start_time
            if result.get(ResponseKey.STATUS.value) == ResponseStatus.SUCCESS.value:
                horizon_angles, zenith_angles = self._parse_response_angles(result)

                if len(horizon_angles) == 0 or len(zenith_angles) == 0:
                    self._logger.error(
                        ObstructionLogTemplate.EMPTY_ANGLES.format(keys=list(result.keys()))
                    )

                direction_angles = config.get_direction_angles(window.direction_angle)

                obstruction_results = []
                for i, (direction_angle, horizon_angle, zenith_angle) in enumerate(
                    zip(direction_angles, horizon_angles, zenith_angles)
                ):
                    obstruction_results.append(ObstructionResult(
                        direction=direction_angle,
                        horizon=horizon_angle,
                        zenith=zenith_angle,
                        horizon_highest_point={},
                        zenith_highest_point={}
                    ))

                self._logger.info(
                    ObstructionLogTemplate.SINGLE_COMPLETED.format(seconds=request_time)
                )
                return obstruction_results
            else:
                error_msg = result.get(ResponseKey.ERROR.value, "Unknown error")
                raise Exception(ObstructionLogTemplate.SERVICE_ERROR.format(error=error_msg))

        except aiohttp.ClientResponseError as e:
            if e.status == 403:
                error = ServiceAuthorizationError(
                    service_name=ServiceName.OBSTRUCTION.value,
                    endpoint=EndpointPathBuilder.path(EndpointType.OBSTRUCTION_PARALLEL.value),
                    error_message=e.message
                )
                self._logger.error(error.get_log_message())
                raise error
            else:
                error = ServiceResponseError(
                    service_name=ServiceName.OBSTRUCTION.value,
                    endpoint=EndpointPathBuilder.path(EndpointType.OBSTRUCTION_PARALLEL.value),
                    status_code=e.status,
                    error_message=e.message
                )
                self._logger.error(error.get_log_message())
                raise error
        except aiohttp.ClientConnectorError as e:
            error = ServiceConnectionError(
                service_name=ServiceName.OBSTRUCTION.value,
                endpoint=EndpointPathBuilder.path(EndpointType.OBSTRUCTION_PARALLEL.value),
                address=self._api_url,
                original_error=e
            )
            self._logger.error(error.get_log_message())
            raise error
        except aiohttp.ClientError as e:
            error = ServiceConnectionError(
                service_name=ServiceName.OBSTRUCTION.value,
                endpoint=EndpointPathBuilder.path(EndpointType.OBSTRUCTION_PARALLEL.value),
                address=self._api_url,
                original_error=e
            )
            self._logger.error(error.get_log_message())
            raise error
        except asyncio.TimeoutError:
            error = ServiceTimeoutError(
                service_name=ServiceName.OBSTRUCTION.value,
                endpoint=EndpointPathBuilder.path(EndpointType.OBSTRUCTION_PARALLEL.value),
                timeout_seconds=config.timeout_seconds
            )
            self._logger.error(error.get_log_message())
            raise error
