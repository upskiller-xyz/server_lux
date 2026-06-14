"""Tests for ObstructionService binary (multipart) mesh forwarding.

When the mesh arrives as raw bytes (.npy / gzip), lux forwards it untouched to
obstruction's ``*_bin`` endpoint as a multipart file instead of embedding it in
a JSON body — so lux never parses the multi-MB mesh.
"""

import io

import numpy as np
from unittest.mock import patch

from src.server.services.remote.obstruction_service import ObstructionService
from src.server.services.remote.contracts import ObstructionRequest
from src.server.enums import EndpointType


def _npy_bytes() -> bytes:
    buf = io.BytesIO()
    np.save(buf, np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32))
    return buf.getvalue()


_FAKE_RESPONSE = {
    "status": "success",
    "data": {"results": [{
        "horizon": {"obstruction_angle_degrees": 12.0},
        "zenith": {"obstruction_angle_degrees": 80.0},
    }]},
}


def test_binary_mesh_forwarded_as_multipart_to_bin_endpoint():
    raw = _npy_bytes()
    request = ObstructionRequest(
        x=0.5, y=0.5, z=10.0, direction_angle=90.0, mesh=raw, window_name="window"
    )

    captured = {}

    def fake_post_multipart(url, files=None, data=None, headers=None):
        captured.update(url=url, files=files, data=data, headers=headers)
        return _FAKE_RESPONSE

    with patch.object(ObstructionService._http_client, "post_multipart", side_effect=fake_post_multipart), \
         patch.object(ObstructionService, "_get_url", return_value="http://obstruction:8080/obstruction_parallel"), \
         patch.object(ObstructionService, "_auth_headers", return_value={}):
        out = ObstructionService.run(EndpointType.OBSTRUCTION_PARALLEL, request)

    # Routed to the binary endpoint, mesh sent as a file (not in the JSON body).
    assert captured["url"].endswith("/obstruction_parallel_bin")
    assert "mesh" not in captured["data"]
    assert "params" in captured["data"]
    assert bytes(captured["files"]["mesh"][1]) == raw
    # Response parsed exactly like the JSON path.
    assert "horizon" in out and "zenith" in out


class _DummyResponse:
    horizon = [1.0]
    zenith = [2.0]


def test_list_mesh_still_uses_json_path():
    request = ObstructionRequest(
        x=0.5, y=0.5, z=10.0, direction_angle=90.0,
        mesh=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], window_name="window",
    )

    with patch("src.server.services.remote.base.RemoteService.run", return_value=_DummyResponse()) as super_run, \
         patch.object(ObstructionService._http_client, "post_multipart") as post_mp:
        ObstructionService.run(EndpointType.OBSTRUCTION_PARALLEL, request)

    # JSON (list) mesh takes the standard path; multipart is never used.
    post_mp.assert_not_called()
    super_run.assert_called_once()


def test_orchestrator_drops_binary_mesh_after_obstruction():
    """Once obstruction has run, the raw binary mesh must be removed from params
    so it never leaks into the encoder/model/merger requests (bytes aren't JSON
    serializable). A JSON (list) mesh is left untouched."""
    from src.server.services.orchestration.orchestrator import Orchestrator
    from src.server.services.remote import EncoderService
    from src.server.enums import RequestField

    orch = Orchestrator()

    # After ObstructionService: bytes mesh dropped.
    params = {RequestField.MESH.value: b"\x93NUMPY-bytes", "horizon": [1], "zenith": [2]}
    orch._drop_binary_mesh(ObstructionService, params)
    assert RequestField.MESH.value not in params

    # Before obstruction (any other service): bytes mesh kept (obstruction needs it).
    params = {RequestField.MESH.value: b"\x93NUMPY-bytes"}
    orch._drop_binary_mesh(EncoderService, params)
    assert RequestField.MESH.value in params

    # JSON list mesh: untouched even after obstruction (backward compatible).
    params = {RequestField.MESH.value: [[0, 0, 0]]}
    orch._drop_binary_mesh(ObstructionService, params)
    assert RequestField.MESH.value in params
