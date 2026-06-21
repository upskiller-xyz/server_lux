from typing import Dict, Any, List, Union, cast
import asyncio
import time
import math
import logging

import orjson

from src.server.services.helpers.parallel import ParallelRequest
from src.server.services.remote.contracts.obstruction_contracts import ObstructionResponse
logger = logging.getLogger("logger")
from .contracts import ObstructionRequest, RemoteServiceRequest, RemoteServiceResponse
# from .contracts import ObstructionResponse
from ...enums import ServiceName, EndpointType, RequestField, ResponseKey, ResponseStatus, HTTPStatus
from ...exceptions import ServiceResponseError
from .base import RemoteService
from ...services.obstruction.calculator_interface import IObstructionCalculator


class ObstructionService(RemoteService):
    """Service for obstruction angle calculations"""
    name: ServiceName = ServiceName.OBSTRUCTION

    # Suffix of the binary (multipart) transport endpoint on obstruction.
    _BIN_SUFFIX: str = "_bin"

    @classmethod
    def _get_request(cls, endpoint: EndpointType) -> type[RemoteServiceRequest]:
        """Get request class for endpoint

        All obstruction endpoints use ObstructionRequest
        """
        return ObstructionRequest

    @classmethod
    def run(cls, endpoint: EndpointType, request: RemoteServiceRequest, file: Any = None, response_class: type[RemoteServiceResponse] = ObstructionResponse) -> Dict[str, Any]:
        """Calculate obstruction angles and format response for orchestration"""
        # Cast to ObstructionRequest since _get_request returns ObstructionRequest
        obstruction_request = cast(ObstructionRequest, request)

        # A binary mesh (.npy / gzip) is forwarded untouched to obstruction's
        # binary endpoint as multipart — lux never parses it. A JSON (list) mesh
        # takes the standard JSON path.
        if isinstance(obstruction_request.mesh, (bytes, bytearray)):
            response = cls._run_binary(obstruction_request, response_class)
        else:
            response = super().run(endpoint, request, file, response_class)
        response = cast(ObstructionResponse, response)

        window_name = obstruction_request.window_name

        # Access attributes directly from the dataclass/object
        horizon_angles = response.horizon if response.horizon is not None else []
        zenith_angles = response.zenith if response.zenith is not None else []

        logger.debug(f"[ObstructionService] Parsed horizon_angles: {horizon_angles}")
        logger.debug(f"[ObstructionService] Parsed zenith_angles: {zenith_angles}")

        # For single-window requests (default window name), return flat structure
        # For multi-window orchestration, return nested structure
        horizon_params = horizon_angles
        zenith_params = zenith_angles
        if window_name != "window":
            horizon_params = {window_name: horizon_angles}
            zenith_params = {window_name: zenith_angles}
        return {
            ResponseKey.HORIZON.value: horizon_params,
            ResponseKey.ZENITH.value: zenith_params
        }

    @classmethod
    def _run_binary(
        cls,
        request: ObstructionRequest,
        response_class: type[RemoteServiceResponse],
    ) -> RemoteServiceResponse:
        """Forward a binary mesh to obstruction's binary endpoint as multipart.

        Binary transport exists only on the parallel endpoint
        (``/obstruction_parallel_bin``), so all binary meshes are routed there
        regardless of which obstruction endpoint the client requested — appending
        ``_bin`` to other endpoints (``/obstruction``, ``/obstruction_multi``,
        ``/horizon``, ``/zenith``) would call routes that don't exist.

        lux never parses the mesh: the raw .npy/gzip bytes are forwarded through
        as a multipart file, with the small window fields in a JSON ``params`` form field. Reuses the same response parsing as the JSON path.
        """
        url = cls._get_url(EndpointType.OBSTRUCTION_PARALLEL) + cls._BIN_SUFFIX
        params = {
            k: v for k, v in request.to_dict.items() if k != RequestField.MESH.value
        }
        # run() only routes here when mesh is bytes/bytearray; bytes() also accepts
        # bytearray, yielding the immutable payload the multipart upload needs.
        mesh_bytes = bytes(cast(Union[bytes, bytearray], request.mesh))
        files = {
            RequestField.MESH.value: ("mesh.npy", mesh_bytes, "application/octet-stream")
        }
        logger.info(f"[{cls.name.value}] Calling binary endpoint: {url}")
        response_dict = cls._http_client.post_multipart(
            url,
            files=files,
            data={"params": orjson.dumps(params).decode()},
            headers=cls._auth_headers(url),
        )
        if response_dict is None:
            raise ServiceResponseError(
                cls.name.value, url, HTTPStatus.BAD_GATEWAY.value,
                "obstruction binary endpoint returned no response",
            )
        return response_class.parse(response_dict)
    

