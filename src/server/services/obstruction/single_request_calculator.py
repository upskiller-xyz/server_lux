import logging
from typing import Dict, Any, List, Optional
import time
import aiohttp
import asyncio
from ...enums import ServiceName, EndpointType, RequestField, ResponseKey, ResponseStatus, HTTPHeader, HTTPContentType
from ...exceptions import ServiceConnectionError, ServiceTimeoutError, ServiceResponseError, ServiceAuthorizationError
from .config import WindowGeometry, ObstructionCalculationConfig, ObstructionResult
from .calculator_interface import IObstructionCalculator


class SingleRequestObstructionCalculator(IObstructionCalculator):

    def __init__(self, api_url: str, api_token: Optional[str] = None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._api_token = api_token
        self._api_url = api_url

    def _parse_response_angles(self, result: Dict[str, Any]) -> tuple[List[float], List[float]]:
        if ResponseKey.HORIZON_ANGLES.value in result and ResponseKey.ZENITH_ANGLES.value in result:
            return (
                result.get(ResponseKey.HORIZON_ANGLES.value, []),
                result.get(ResponseKey.ZENITH_ANGLES.value, [])
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

        self._logger.error(f"Unknown response format! Keys: {list(result.keys())}")
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
            headers[HTTPHeader.AUTHORIZATION.value] = f"Bearer {self._api_token}"

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
                    self._logger.error(f"Empty angle arrays! Response keys: {list(result.keys())}")

                direction_angles = config.get_direction_angles(window.direction_angle)

                obstruction_results = []
                for i, (direction_angle, horizon_angle, zenith_angle) in enumerate(
                    zip(direction_angles, horizon_angles, zenith_angles)
                ):
                    obstruction_results.append(ObstructionResult(
                        direction_angle=direction_angle,
                        horizon_angle=horizon_angle,
                        zenith_angle=zenith_angle,
                        horizon_highest_point={},
                        zenith_highest_point={}
                    ))

                self._logger.info(f"Completed obstruction calculation in {request_time:.2f}s")
                return obstruction_results
            else:
                error_msg = result.get(ResponseKey.ERROR.value, "Unknown error")
                raise Exception(f"Obstruction service error: {error_msg}")

        except aiohttp.ClientResponseError as e:
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
            error = ServiceConnectionError(
                service_name=ServiceName.OBSTRUCTION.value,
                endpoint=f"/{EndpointType.OBSTRUCTION_PARALLEL.value}",
                address=self._api_url,
                original_error=e
            )
            self._logger.error(error.get_log_message())
            raise error
        except aiohttp.ClientError as e:
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
