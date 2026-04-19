"""Unit tests for model spec pipeline components"""

import pytest
from unittest.mock import MagicMock, patch

from src.server.enums import RequestField
from src.server.services.remote.contracts.model_spec_contracts import (
    ModelSpecRequest,
    ModelSpecResponse,
)
from src.server.services.remote.contracts.main_request_contract import MainRequest


class TestModelSpecRequest:

    def test_parse_reads_model_type_as_model_name(self):
        content = {RequestField.MODEL_TYPE.value: "019da240-uuid"}
        requests = ModelSpecRequest.parse(content)
        assert len(requests) == 1
        assert requests[0].model_name == "019da240-uuid"

    def test_to_dict_returns_model_query_param(self):
        req = ModelSpecRequest(model_name="019da240-uuid")
        assert req.to_dict == {"model": "019da240-uuid"}

    def test_parse_empty_model_type(self):
        requests = ModelSpecRequest.parse({})
        assert requests[0].model_name == ""


class TestModelSpecResponse:

    def test_parse_extracts_encoding_scheme_and_model_type(self):
        data = {
            RequestField.ENCODING_SCHEME.value: "v5",
            RequestField.ENCODER_MODEL_TYPE.value: "df_default",
        }
        resp = ModelSpecResponse.parse(data)
        assert resp.encoding_scheme == "v5"
        assert resp.encoder_model_type == "df_default"

    def test_to_dict_includes_both_fields(self):
        resp = ModelSpecResponse(encoding_scheme="v5", encoder_model_type="df_default")
        d = resp.to_dict
        assert d[RequestField.ENCODING_SCHEME.value] == "v5"
        assert d[RequestField.ENCODER_MODEL_TYPE.value] == "df_default"

    def test_to_dict_omits_none_fields(self):
        resp = ModelSpecResponse(encoding_scheme=None, encoder_model_type=None)
        assert resp.to_dict == {}

    def test_parse_missing_fields_returns_none(self):
        resp = ModelSpecResponse.parse({})
        assert resp.encoding_scheme is None
        assert resp.encoder_model_type is None


class TestMainRequestWithSpec:

    def _make_params(self, **kwargs):
        """Minimal params dict for MainRequest.parse()"""
        base = {
            RequestField.PARAMETERS.value: {
                RequestField.WINDOWS.value: {
                    "w1": {"x1": 0, "y1": 0, "z1": 0, "x2": 1, "y2": 0, "z2": 2}
                },
                RequestField.ROOM_POLYGON.value: [[0, 0], [1, 0], [1, 1], [0, 1]],
            },
            RequestField.MESH.value: [],
        }
        base.update(kwargs)
        return base

    def test_uses_encoder_model_type_over_model_type(self):
        params = self._make_params(**{
            RequestField.MODEL_TYPE.value: "019da240-uuid",
            RequestField.ENCODER_MODEL_TYPE.value: "df_default",
        })
        requests = MainRequest.parse(params)
        assert requests[0].model_type == "df_default"

    def test_falls_back_to_model_type_when_encoder_model_type_missing(self):
        params = self._make_params(**{
            RequestField.MODEL_TYPE.value: "df_default_2.0.1",
        })
        requests = MainRequest.parse(params)
        assert requests[0].model_type == "df_default_2.0.1"

    def test_encoding_scheme_included_in_to_dict_when_present(self):
        params = self._make_params(**{
            RequestField.MODEL_TYPE.value: "uuid",
            RequestField.ENCODER_MODEL_TYPE.value: "df_default",
            RequestField.ENCODING_SCHEME.value: "v5",
        })
        requests = MainRequest.parse(params)
        d = requests[0].to_dict
        assert d[RequestField.ENCODING_SCHEME.value] == "v5"
        assert d[RequestField.MODEL_TYPE.value] == "df_default"

    def test_encoding_scheme_absent_from_to_dict_when_not_set(self):
        params = self._make_params(**{
            RequestField.MODEL_TYPE.value: "df_default",
        })
        requests = MainRequest.parse(params)
        assert RequestField.ENCODING_SCHEME.value not in requests[0].to_dict
