import logging
import os
import threading
import time
from typing import Any, Dict, Union, cast

import orjson

from src.server.services.remote.contracts.obstruction_contracts import (
    ObstructionResponse,
)

from ...constants import ObstructionConcurrency, ObstructionRequestDefaults
from ...enums import (
    EndpointType,
    HTTPStatus,
    RequestField,
    ResponseKey,
    ServiceName,
)
from ...exceptions import ServiceResponseError
from ...services.helpers.call_recorder import CallRecorder
from ...services.obstruction.empty_mesh_policy import EmptyMeshPolicy
from .base import RemoteService
from .contracts import ObstructionRequest, RemoteServiceRequest, RemoteServiceResponse

logger = logging.getLogger("logger")


def _resolve_obstruction_concurrency() -> int:
    """Resolve OBSTRUCTION_MAX_CONCURRENCY into a valid semaphore size.

    Falls back to the default on a missing/non-integer value (a bad value would
    otherwise raise ValueError at import and stop the server from starting) and
    floors at 1 (a value <= 0 would deadlock every obstruction call on the
    semaphore).
    """
    raw = os.getenv(ObstructionConcurrency.MAX_ENV)
    if raw is None:
        return ObstructionConcurrency.DEFAULT_MAX
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "Invalid %s=%r; falling back to %s",
            ObstructionConcurrency.MAX_ENV,
            raw,
            ObstructionConcurrency.DEFAULT_MAX,
        )
        return ObstructionConcurrency.DEFAULT_MAX
    return max(1, value)


class SemaphoreWaitTimer:
    """Measures the time spent acquiring the concurrency semaphore.

    The [call] record for the obstruction call measures only the remote hop
    (the recorder sits inside the gate), so a burst queuing on the semaphore
    would be invisible — the exact blind spot the Modal finding was about
    (queue, not execution). The measured wait is stamped onto the call's
    record as ``wait_ms`` before the recorder emits it.
    """

    def __init__(self):
        self._t0 = 0.0
        self.wait_ms: float | None = None

    def __enter__(self) -> "SemaphoreWaitTimer":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self.wait_ms = (time.perf_counter() - self._t0) * 1000
        return False  # never suppress exceptions


class ObstructionService(RemoteService):
    """Service for obstruction angle calculations"""
    name: ServiceName = ServiceName.OBSTRUCTION

    # Suffix of the binary (multipart) transport endpoint on obstruction.
    _BIN_SUFFIX: str = "_bin"

    # Backpressure: cap concurrent in-flight obstruction requests per lux process
    # so the per-window fan-out cannot flood the backend past its capacity. The
    # remote calls run in ThreadPoolExecutor threads (sync requests), so this is a
    # thread — not asyncio — semaphore. Sized from the environment to match the
    # backend ceiling (e.g. Scaleway serverless max-instances).
    _concurrency_limit: int = _resolve_obstruction_concurrency()
    _concurrency: threading.BoundedSemaphore = threading.BoundedSemaphore(_concurrency_limit)

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

        # No context geometry means nothing shades the window: 0° in every
        # direction, known without the remote service. Returning here also keeps
        # the request off the concurrency semaphore, so a room whose windows have
        # no obstruction mesh costs no obstruction capacity at all.
        if EmptyMeshPolicy.is_empty(obstruction_request.mesh):
            return EmptyMeshPolicy.unobstructed_angles(obstruction_request.window_name)

        # A binary mesh (.npy / gzip) is forwarded untouched to obstruction's
        # binary endpoint as multipart — lux never parses it. A JSON (list) mesh
        # takes the standard JSON path. Both remote calls are gated by the
        # concurrency semaphore so a burst of windows queues here instead of
        # overwhelming the obstruction backend. The gate wait is measured and
        # stamped onto the call's [call] record as wait_ms — without it, the
        # record sees only the hop and a queuing burst is invisible.
        gate = SemaphoreWaitTimer()
        with cls._concurrency, gate:
            if isinstance(obstruction_request.mesh, (bytes, bytearray)):
                response = cls._run_binary(obstruction_request, response_class, gate.wait_ms)
            else:
                response = super().run(endpoint, request, file, response_class, gate.wait_ms)
        response = cast(ObstructionResponse, response)

        window_name = obstruction_request.window_name

        # Access attributes directly from the dataclass/object
        horizon_angles = response.horizon if response.horizon is not None else []
        zenith_angles = response.zenith if response.zenith is not None else []

        logger.debug("[ObstructionService] Parsed horizon_angles: %s", horizon_angles)
        logger.debug("[ObstructionService] Parsed zenith_angles: %s", zenith_angles)

        # For single-window requests (default window name), return flat structure
        # For multi-window orchestration, return nested structure
        horizon_params = horizon_angles
        zenith_params = zenith_angles
        if window_name != ObstructionRequestDefaults.WINDOW_NAME:
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
        wait_ms: float | None = None,
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
        endpoint = cls._binary_endpoint()
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
        logger.info("[%s] Calling binary endpoint: %s", cls.name.value, url)
        recorder = CallRecorder(cls.name, endpoint)
        if wait_ms is not None:
            recorder.record_wait(wait_ms)
        with recorder:
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

    @classmethod
    def _binary_endpoint(cls) -> str:
        """The endpoint label for the binary transport route — one place, so
        the [call] record's endpoint cannot drift from the URL actually called."""
        return EndpointType.OBSTRUCTION_PARALLEL.value + cls._BIN_SUFFIX
    

