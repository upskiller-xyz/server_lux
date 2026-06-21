"""Unit tests for RequestParser.extract_params (orjson body parsing + fallback +
multipart mesh pass-through)."""

import gzip
import io

import numpy as np
import orjson
from flask import Flask, request

from src.server.request_handler import RequestParser

app = Flask(__name__)


def _multipart_ctx(params: dict, mesh):
    return app.test_request_context(
        method="POST",
        data={
            "params": orjson.dumps(params).decode(),
            "mesh": (io.BytesIO(orjson.dumps(mesh)), "mesh.json"),
        },
        content_type="multipart/form-data",
    )


def _multipart_bin_ctx(params: dict, mesh_bytes: bytes):
    return app.test_request_context(
        method="POST",
        data={
            "params": orjson.dumps(params).decode(),
            "mesh": (io.BytesIO(mesh_bytes), "mesh.npy"),
        },
        content_type="multipart/form-data",
    )


def _npy_bytes() -> bytes:
    buf = io.BytesIO()
    np.save(buf, np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32))
    return buf.getvalue()


def test_parses_json_body_via_orjson():
    body = orjson.dumps({"model_type": "df_default", "parameters": {"x": 1}})
    with app.test_request_context(data=body, content_type="application/json"):
        assert RequestParser.extract_params(request) == {
            "model_type": "df_default",
            "parameters": {"x": 1},
        }


def test_malformed_json_falls_back_to_form():
    with app.test_request_context(data=b"{not json", content_type="application/json"):
        # orjson raises → form fallback (no form fields here → empty dict).
        assert RequestParser.extract_params(request) == {}


def test_non_json_uses_form():
    with app.test_request_context(data={"a": "1", "b": "2"}):  # multipart/form-encoded
        assert RequestParser.extract_params(request) == {"a": "1", "b": "2"}


def test_multipart_parses_mesh_when_obstruction_runs():
    # No pre-calculated horizon/zenith → obstruction runs → mesh is needed → parsed.
    params = {"model_type": "df_default", "parameters": {}}
    with _multipart_ctx(params, [[1.0, 2.0, 3.0]]):
        out = RequestParser.extract_params(request)
        assert out["model_type"] == "df_default"
        assert out["mesh"] == [[1.0, 2.0, 3.0]]


def test_multipart_skips_mesh_when_precalc_horizon_zenith():
    # Pre-calculated horizon+zenith → obstruction skipped → mesh never parsed (empty).
    params = {"model_type": "df_default", "horizon": {"w": []}, "zenith": {"w": []}}
    with _multipart_ctx(params, [[1.0, 2.0, 3.0]]):
        out = RequestParser.extract_params(request)
        assert out["mesh"] == []


def test_multipart_keeps_npy_mesh_as_raw_bytes():
    # A binary .npy mesh is never parsed by lux — forwarded as raw bytes.
    raw = _npy_bytes()
    params = {"model_type": "df_default", "parameters": {}}
    with _multipart_bin_ctx(params, raw):
        out = RequestParser.extract_params(request)
        assert isinstance(out["mesh"], (bytes, bytearray))
        assert bytes(out["mesh"]) == raw


def test_multipart_keeps_gzipped_npy_mesh_as_raw_bytes():
    gz = gzip.compress(_npy_bytes())
    params = {"model_type": "df_default", "parameters": {}}
    with _multipart_bin_ctx(params, gz):
        out = RequestParser.extract_params(request)
        assert isinstance(out["mesh"], (bytes, bytearray))
        assert bytes(out["mesh"]) == gz


def test_binary_mesh_dropped_when_obstruction_skipped():
    # Even a binary mesh is dropped when obstruction is skipped.
    params = {"model_type": "df_default", "horizon": {"w": []}, "zenith": {"w": []}}
    with _multipart_bin_ctx(params, _npy_bytes()):
        assert RequestParser.extract_params(request)["mesh"] == []


def test_is_binary_mesh_detection():
    assert RequestParser._is_binary_mesh(_npy_bytes()) is True
    assert RequestParser._is_binary_mesh(gzip.compress(_npy_bytes())) is True
    assert RequestParser._is_binary_mesh(orjson.dumps([[0, 0, 0]])) is False
