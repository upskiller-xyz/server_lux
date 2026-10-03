"""Tests for empty-mesh handling (issue #56).

A request without context geometry means nothing shades the window: obstruction
angles are 0° in every direction, and the remote obstruction service must not be
called at all.
"""

import io

import numpy as np
import pytest
from unittest.mock import patch

from src.server.constants import ObstructionAngleDefaults, ObstructionRequestDefaults
from src.server.controllers.validation_strategy import ValidationStrategy
from src.server.enums import EndpointType, RequestField
from src.server.exceptions import RequestValidationError
from src.server.services.obstruction.empty_mesh_policy import EmptyMeshPolicy
from src.server.services.orchestration.service_executor import ExecutorFactory
from src.server.services.remote.contracts import ObstructionRequest
from src.server.services.remote.obstruction_service import ObstructionService

_COUNT = ObstructionAngleDefaults.EXPECTED_ANGLE_COUNT
_DEFAULT_WINDOW = ObstructionRequestDefaults.WINDOW_NAME


def _npy_bytes() -> bytes:
    buf = io.BytesIO()
    np.save(buf, np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32))
    return buf.getvalue()


class TestEmptyMeshPolicyDetection:
    """is_empty() across every shape the mesh field accepts."""

    @pytest.mark.parametrize("mesh", [
        None,
        [],
        {},
        {"horizon": [], "zenith": []},
        b"",
        bytearray(),
    ], ids=["none", "empty_list", "empty_dict", "empty_split", "empty_bytes", "empty_bytearray"])
    def test_empty_shapes_are_detected(self, mesh):
        assert EmptyMeshPolicy.is_empty(mesh) is True

    @pytest.mark.parametrize("mesh", [
        [[0.0, 0.0, 0.0]],
        {"horizon": [[0.0, 0.0, 0.0]], "zenith": []},
        {"zenith": [[0.0, 0.0, 0.0]]},
    ], ids=["list", "split_horizon_only", "split_zenith_only"])
    def test_geometry_is_not_empty(self, mesh):
        assert EmptyMeshPolicy.is_empty(mesh) is False

    def test_binary_payload_with_content_is_not_empty(self):
        # lux never parses .npy/gzip, so only a zero-length payload counts as
        # empty; the obstruction service resolves the rest itself.
        assert EmptyMeshPolicy.is_empty(_npy_bytes()) is False


class TestUnobstructedAngles:
    """The zero-angle answer, in both response shapes."""

    def test_default_window_returns_flat_lists(self):
        angles = EmptyMeshPolicy.unobstructed_angles()

        assert angles["horizon"] == [0.0] * _COUNT
        assert angles["zenith"] == [0.0] * _COUNT

    def test_named_window_returns_nested_mapping(self):
        angles = EmptyMeshPolicy.unobstructed_angles("window_1")

        assert angles["horizon"] == {"window_1": [0.0] * _COUNT}
        assert angles["zenith"] == {"window_1": [0.0] * _COUNT}

    def test_horizon_and_zenith_are_independent_lists(self):
        # A shared list would let a later mutation of one leak into the other.
        angles = EmptyMeshPolicy.unobstructed_angles()

        assert angles["horizon"] is not angles["zenith"]


class TestObstructionServiceSkipsRemoteCall:
    """ObstructionService.run() answers locally for an empty mesh."""

    @staticmethod
    def _request(mesh, window_name=_DEFAULT_WINDOW) -> ObstructionRequest:
        return ObstructionRequest(
            x=0.5, y=0.5, z=10.0, direction_angle=90.0, mesh=mesh, window_name=window_name
        )

    @pytest.mark.parametrize("mesh", [None, [], b""], ids=["none", "empty_list", "empty_bytes"])
    def test_no_http_request_is_made(self, mesh):
        with patch.object(ObstructionService._http_client, "post") as post, \
             patch.object(ObstructionService._http_client, "post_multipart") as post_multipart:
            out = ObstructionService.run(EndpointType.OBSTRUCTION_PARALLEL, self._request(mesh))

        post.assert_not_called()
        post_multipart.assert_not_called()
        assert out["horizon"] == [0.0] * _COUNT
        assert out["zenith"] == [0.0] * _COUNT

    def test_named_window_keeps_orchestration_shape(self):
        with patch.object(ObstructionService._http_client, "post") as post:
            out = ObstructionService.run(
                EndpointType.OBSTRUCTION_PARALLEL, self._request([], window_name="window_2")
            )

        post.assert_not_called()
        assert out["horizon"] == {"window_2": [0.0] * _COUNT}
        assert out["zenith"] == {"window_2": [0.0] * _COUNT}

    def test_concurrency_semaphore_is_not_taken(self):
        # An empty mesh must not consume obstruction capacity: the semaphore is
        # left untouched, so these requests cannot queue behind real work.
        before = ObstructionService._concurrency._value

        ObstructionService.run(EndpointType.OBSTRUCTION_PARALLEL, self._request([]))

        assert ObstructionService._concurrency._value == before


class TestMultiWindowOrchestration:
    """The per-window fan-out an orchestrated /run produces."""

    def test_every_window_gets_zero_angles_without_any_remote_call(self):
        # What ReferencePointService leaves in params before obstruction runs,
        # with no mesh in the request at all.
        params = {
            RequestField.REFERENCE_POINT.value: {
                "window_1": {"x": 1.0, "y": 2.0, "z": 3.0},
                "window_2": {"x": 4.0, "y": 5.0, "z": 6.0},
            },
            RequestField.DIRECTION_ANGLE.value: {"window_1": 90.0, "window_2": 180.0},
        }
        requests = ObstructionRequest.parse(params)
        executor = ExecutorFactory.create(len(requests))

        with patch.object(ObstructionService._http_client, "post") as post, \
             patch.object(ObstructionService._http_client, "post_multipart") as post_multipart:
            out = executor.execute(
                ObstructionService, EndpointType.OBSTRUCTION_PARALLEL, requests, None
            )

        post.assert_not_called()
        post_multipart.assert_not_called()
        assert out["horizon"] == {"window_1": [0.0] * _COUNT, "window_2": [0.0] * _COUNT}
        assert out["zenith"] == {"window_1": [0.0] * _COUNT, "window_2": [0.0] * _COUNT}


class TestMeshFieldValidation:
    """Mesh is optional, but still type-checked when present."""

    _RUN_FIELDS = [RequestField.MODEL_TYPE, RequestField.PARAMETERS, RequestField.MESH]

    def test_absent_mesh_passes_validation(self):
        ValidationStrategy.validate_fields(
            {RequestField.MODEL_TYPE.value: "df", RequestField.PARAMETERS.value: {}},
            self._RUN_FIELDS,
        )

    def test_empty_mesh_passes_validation(self):
        ValidationStrategy.validate_fields(
            {
                RequestField.MODEL_TYPE.value: "df",
                RequestField.PARAMETERS.value: {},
                RequestField.MESH.value: [],
            },
            self._RUN_FIELDS,
        )

    @pytest.mark.parametrize("mesh", [
        {},
        {"horizon": [], "zenith": []},
        {"horizon": [[0.0, 0.0, 0.0]], "zenith": []},
    ], ids=["empty_dict", "empty_split", "split_with_geometry"])
    def test_split_dict_mesh_passes_validation(self, mesh):
        # ObstructionMultiRequest sends the split form, and EmptyMeshPolicy
        # recognises the empty variants — neither is reachable if validation
        # rejects dicts outright.
        ValidationStrategy.validate_fields(
            {
                RequestField.MODEL_TYPE.value: "df",
                RequestField.PARAMETERS.value: {},
                RequestField.MESH.value: mesh,
            },
            self._RUN_FIELDS,
        )

    def test_wrong_mesh_type_is_rejected(self):
        with pytest.raises(RequestValidationError, match="mesh"):
            ValidationStrategy.validate_fields(
                {
                    RequestField.MODEL_TYPE.value: "df",
                    RequestField.PARAMETERS.value: {},
                    RequestField.MESH.value: "not-a-mesh",
                },
                self._RUN_FIELDS,
            )

    def test_other_required_fields_still_enforced(self):
        with pytest.raises(RequestValidationError, match=RequestField.MODEL_TYPE.value):
            ValidationStrategy.validate_fields(
                {RequestField.PARAMETERS.value: {}}, self._RUN_FIELDS
            )

    def test_missing_parameters_still_rejected(self):
        with pytest.raises(RequestValidationError, match=RequestField.PARAMETERS.value):
            ValidationStrategy.validate_fields(
                {RequestField.MODEL_TYPE.value: "df"}, self._RUN_FIELDS
            )
