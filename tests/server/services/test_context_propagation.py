"""Tests for correlation-id propagation through the per-window fan-out.

``run_in_executor`` does not copy the calling context into its worker threads,
so a request id set on the request thread was invisible inside the fan-out —
every per-window ``[call]`` record lost its rid. The switch to
``asyncio.to_thread`` (which uses ``contextvars.copy_context()``) is what
makes one pipeline run's calls reassemblable; these tests pin that behavior.
"""

import pytest

from src.server.enums import EndpointType, RequestField
from src.server.exceptions import RequestValidationError
from src.server.services.helpers.call_recorder import (
    UNKNOWN_REQUEST_ID,
    RequestIdContext,
)
from src.server.services.orchestration.service_executor import (
    ParallelServiceExecutor,
)
from src.server.services.orchestration.window_processor import WindowProcessor


def _multi_window_request(window_names):
    return {
        RequestField.PARAMETERS.value: {
            RequestField.WINDOWS.value: {
                name: {"x1": 0, "y1": 0, "z1": 0, "x2": 1, "y2": 0, "z2": 2}
                for name in window_names
            },
            RequestField.ROOM_POLYGON.value: [[0, 0], [1, 0], [1, 1], [0, 1]],
        },
        RequestField.MESH.value: [],
    }


class _RidCaptureService:
    """Stand-in service: records the request id each worker thread saw."""

    seen = []

    @classmethod
    def reset(cls):
        cls.seen = []

    @staticmethod
    def run(endpoint, request, file=None):
        # request is a window-name string from the fan-out — usable as a key.
        rid = RequestIdContext.get()
        _RidCaptureService.seen.append(rid)
        return {RequestField.HORIZON.value: {request: [1.0]}}


class TestParallelServiceExecutorContextPropagation:

    def test_rid_follows_each_parallel_call_into_worker_threads(self):
        _RidCaptureService.reset()
        token = RequestIdContext.set("run-42")
        try:
            ParallelServiceExecutor().execute(
                _RidCaptureService,
                EndpointType.OBSTRUCTION_PARALLEL,
                ["window_1", "window_2", "window_3"],
                None,
            )
        finally:
            RequestIdContext.reset(token)

        assert _RidCaptureService.seen == ["run-42", "run-42", "run-42"]

    def test_no_rid_outside_a_request_stays_unknown_inside_threads(self):
        _RidCaptureService.reset()
        ParallelServiceExecutor().execute(
            _RidCaptureService, EndpointType.OBSTRUCTION_PARALLEL, ["w1"], None
        )

        assert _RidCaptureService.seen == [UNKNOWN_REQUEST_ID]


class TestWindowProcessorContextPropagation:

    def test_rid_survives_the_per_window_fan_out(self):
        _RidCaptureService.reset()
        processor = WindowProcessor(orchestrator=None)

        class _Orchestrator:
            def run(self, endpoint, request, file):
                # WindowProcessor passes a single-window dict request; the
                # worker-thread read below is the actual propagation assert.
                rid = RequestIdContext.get()
                _RidCaptureService.seen.append(rid)
                window_name = request[RequestField.PARAMETERS.value][RequestField.WINDOWS.value]
                name = next(iter(window_name))
                return (name, {RequestField.HORIZON.value: [1.0]})

        processor._orchestrator = _Orchestrator()

        token = RequestIdContext.set("run-99")
        try:
            results = processor.process_all_windows(
                EndpointType.OBSTRUCTION_PARALLEL,
                _multi_window_request(["window_1", "window_2"]),
                None,
            )
        finally:
            RequestIdContext.reset(token)

        # Two windows, each seeing the request's id inside its worker thread.
        assert sorted(_RidCaptureService.seen) == ["run-99", "run-99"]
        assert sorted(name for name, _ in results) == ["window_1", "window_2"]

    def test_missing_windows_raise_validation_error(self):
        processor = WindowProcessor(orchestrator=None)
        with pytest.raises(RequestValidationError):
            processor.process_all_windows(EndpointType.OBSTRUCTION_PARALLEL, {}, None)