"""Tests for the parallel service executor's response merging.

Per-window services answer with a window-keyed mapping under a shared key
(``{"horizon": {"window_1": [...]}}``). Merging those with a plain
``dict.update`` kept only the last window — every other window's angles were
silently dropped on endpoints that fan out several windows in one orchestrator
run (``/obstruction_all``).
"""

from src.server.enums import EndpointType
from src.server.services.orchestration.service_executor import (
    ExecutorFactory,
    ParallelServiceExecutor,
    SingleServiceExecutor,
)


class _PerWindowService:
    """Stand-in for a service answering with a window-keyed mapping."""

    @staticmethod
    def run(endpoint, request, file=None):
        return {
            "horizon": {request: [1.0]},
            "zenith": {request: [2.0]},
        }


class _FlatService:
    """Stand-in for a service answering with scalar values."""

    @staticmethod
    def run(endpoint, request, file=None):
        return {"status": request}


class TestExecutorFactory:

    def test_single_request_uses_single_executor(self):
        assert isinstance(ExecutorFactory.create(1), SingleServiceExecutor)

    def test_multiple_requests_use_parallel_executor(self):
        assert isinstance(ExecutorFactory.create(2), ParallelServiceExecutor)


class _DataclassResponseService:
    """Stand-in for a service answering with a response object, not a dict.

    ReferencePointService and ExternalReferencePointService both do this: their
    ``run()`` returns a response dataclass carrying a ``to_dict`` property.
    """

    @staticmethod
    def run(endpoint, request, file=None):
        class _Response:
            @property
            def to_dict(self):
                return {"reference_point": {request: {"x": 1.0, "y": 2.0, "z": 3.0}}}

        return _Response()


class TestParallelMerge:

    def test_window_keyed_mappings_are_merged_not_replaced(self):
        out = ParallelServiceExecutor().execute(
            _PerWindowService, EndpointType.OBSTRUCTION_PARALLEL, ["window_1", "window_2"], None
        )

        assert out["horizon"] == {"window_1": [1.0], "window_2": [1.0]}
        assert out["zenith"] == {"window_1": [2.0], "window_2": [2.0]}

    def test_non_dict_values_keep_last_wins(self):
        out = ParallelServiceExecutor().execute(
            _FlatService, EndpointType.OBSTRUCTION_PARALLEL, ["first", "second"], None
        )

        assert out["status"] == "second"

    def test_response_dataclasses_are_normalized_and_merged(self):
        # Accepting only dicts dropped every result, leaving an empty merge and
        # no reference points for the obstruction step that follows.
        out = ParallelServiceExecutor().execute(
            _DataclassResponseService,
            EndpointType.REFERENCE_POINT,
            ["window_1", "window_2"],
            None,
        )

        assert out["reference_point"] == {
            "window_1": {"x": 1.0, "y": 2.0, "z": 3.0},
            "window_2": {"x": 1.0, "y": 2.0, "z": 3.0},
        }

    def test_unmergeable_responses_are_ignored(self):
        class _OpaqueService:
            @staticmethod
            def run(endpoint, request, file=None):
                return object()

        out = ParallelServiceExecutor().execute(
            _OpaqueService, EndpointType.REFERENCE_POINT, ["a", "b"], None
        )

        assert out == {}

    def test_binary_response_short_circuits(self):
        class _BinaryService:
            @staticmethod
            def run(endpoint, request, file=None):
                return b"npz-bytes"

        out = ParallelServiceExecutor().execute(
            _BinaryService, EndpointType.ENCODE, ["a", "b"], None
        )

        assert out == b"npz-bytes"
