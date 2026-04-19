"""Unit tests for ModelRequest and CondVecBuilder"""

import math
import numpy as np
import pytest

from src.server.enums import RequestField
from src.server.services.remote.contracts.model_contracts import CondVecBuilder, ModelRequest


def _make_content(**kwargs):
    """Minimal content dict for CondVecBuilder.build() / ModelRequest.parse()."""
    base = {
        RequestField.PARAMETERS.value: {
            RequestField.WINDOWS.value: {
                "w1": {
                    RequestField.X1.value: -0.5,
                    RequestField.Y1.value: 0.0,
                    RequestField.Z1.value: 0.9,
                    RequestField.X2.value: 0.5,
                    RequestField.Y2.value: 0.0,
                    RequestField.Z2.value: 1.8,
                    RequestField.WINDOW_FRAME_RATIO.value: 0.2,
                }
            },
            RequestField.ROOF_HEIGHT.value: 15.0,
            RequestField.FLOOR_HEIGHT.value: 2.0,
        },
        RequestField.DIRECTION_ANGLE.value: {"w1": math.pi / 2},
    }
    base.update(kwargs)
    return base


class TestCondVecBuilderV5:

    def test_returns_none_when_no_encoding_scheme(self):
        content = _make_content()
        assert CondVecBuilder.build(content) is None

    def test_returns_none_for_unknown_scheme(self):
        content = _make_content(**{RequestField.ENCODING_SCHEME.value: "v2"})
        assert CondVecBuilder.build(content) is None

    def test_returns_array_for_v5(self):
        content = _make_content(**{RequestField.ENCODING_SCHEME.value: "v5"})
        vec = CondVecBuilder.build(content)
        assert vec is not None
        assert isinstance(vec, np.ndarray)

    def test_output_has_6_dimensions(self):
        content = _make_content(**{RequestField.ENCODING_SCHEME.value: "v5"})
        vec = CondVecBuilder.build(content)
        assert vec.shape == (6,)

    def test_output_dtype_is_float32(self):
        content = _make_content(**{RequestField.ENCODING_SCHEME.value: "v5"})
        vec = CondVecBuilder.build(content)
        assert vec.dtype == np.float32

    def test_all_values_in_0_1_range(self):
        content = _make_content(**{RequestField.ENCODING_SCHEME.value: "v5"})
        vec = CondVecBuilder.build(content)
        assert np.all(vec >= 0.0)
        assert np.all(vec <= 1.0)

    def test_roof_height_normalised_correctly(self):
        # height_roof_over_floor=15.0, normalised to [0, 30] → 0.5
        content = _make_content(**{RequestField.ENCODING_SCHEME.value: "v5"})
        vec = CondVecBuilder.build(content)
        assert vec[0] == pytest.approx(15.0 / 30.0)

    def test_floor_height_normalised_correctly(self):
        # floor_height_above_terrain=2.0, normalised to [0, 10] → 0.2
        content = _make_content(**{RequestField.ENCODING_SCHEME.value: "v5"})
        vec = CondVecBuilder.build(content)
        assert vec[1] == pytest.approx(2.0 / 10.0)

    def test_window_height_derived_from_z_coordinates(self):
        # z1=0.9, z2=1.8 → win_height=0.9; normalised: 1 - (0.9-0.2)/4.8
        content = _make_content(**{RequestField.ENCODING_SCHEME.value: "v5"})
        vec = CondVecBuilder.build(content)
        expected = 1.0 - (0.9 - 0.2) / 4.8
        assert vec[2] == pytest.approx(expected, abs=1e-5)

    def test_window_width_derived_from_xy_coordinates(self):
        # x1=-0.5, x2=0.5, y1=y2=0 → win_width=1.0; normalised to [0.5, 5.0] → 1.0/5.0=0.2
        content = _make_content(**{RequestField.ENCODING_SCHEME.value: "v5"})
        vec = CondVecBuilder.build(content)
        assert vec[3] == pytest.approx(1.0 / 5.0)

    def test_frame_ratio_inverted(self):
        # window_frame_ratio=0.2 → 1 - 0.2 = 0.8
        content = _make_content(**{RequestField.ENCODING_SCHEME.value: "v5"})
        vec = CondVecBuilder.build(content)
        assert vec[4] == pytest.approx(0.8)

    def test_direction_angle_normalised(self):
        # dir_angle=π/2, normalised to [0, 2π] → 0.25
        content = _make_content(**{RequestField.ENCODING_SCHEME.value: "v5"})
        vec = CondVecBuilder.build(content)
        assert vec[5] == pytest.approx(0.25)

    def test_direction_angle_as_scalar(self):
        content = _make_content(**{RequestField.ENCODING_SCHEME.value: "v5"})
        content[RequestField.DIRECTION_ANGLE.value] = math.pi  # scalar, not dict
        vec = CondVecBuilder.build(content)
        assert vec[5] == pytest.approx(0.5)

    def test_returns_none_when_no_windows(self):
        content = {
            RequestField.ENCODING_SCHEME.value: "v5",
            RequestField.PARAMETERS.value: {},
        }
        assert CondVecBuilder.build(content) is None

    def test_roof_height_clamped_above_30(self):
        content = _make_content(**{RequestField.ENCODING_SCHEME.value: "v5"})
        content[RequestField.PARAMETERS.value][RequestField.ROOF_HEIGHT.value] = 999.0
        vec = CondVecBuilder.build(content)
        assert vec[0] == pytest.approx(1.0)

    def test_floor_height_clamped_above_10(self):
        content = _make_content(**{RequestField.ENCODING_SCHEME.value: "v5"})
        content[RequestField.PARAMETERS.value][RequestField.FLOOR_HEIGHT.value] = 999.0
        vec = CondVecBuilder.build(content)
        assert vec[1] == pytest.approx(1.0)


class TestModelRequestParse:

    def _make_parse_content(self, encoding_scheme=None):
        content = {
            RequestField.IMAGE.value: b"fake_image_bytes",
            RequestField.MODEL_TYPE.value: "df_default",
            RequestField.PARAMETERS.value: {
                RequestField.WINDOWS.value: {
                    "w1": {
                        RequestField.X1.value: -0.5,
                        RequestField.Y1.value: 0.0,
                        RequestField.Z1.value: 0.9,
                        RequestField.X2.value: 0.5,
                        RequestField.Y2.value: 0.0,
                        RequestField.Z2.value: 1.8,
                        RequestField.WINDOW_FRAME_RATIO.value: 0.2,
                    }
                },
                RequestField.ROOF_HEIGHT.value: 15.0,
                RequestField.FLOOR_HEIGHT.value: 2.0,
            },
            RequestField.DIRECTION_ANGLE.value: {"w1": math.pi / 2},
        }
        if encoding_scheme:
            content[RequestField.ENCODING_SCHEME.value] = encoding_scheme
        return content

    def test_parse_sets_cond_vec_for_v5(self):
        requests = ModelRequest.parse(self._make_parse_content(encoding_scheme="v5"))
        assert requests[0].cond_vec is not None
        assert requests[0].cond_vec.shape == (6,)

    def test_parse_cond_vec_is_none_without_encoding_scheme(self):
        requests = ModelRequest.parse(self._make_parse_content())
        assert requests[0].cond_vec is None

    def test_parse_cond_vec_is_none_for_non_cond_vec_scheme(self):
        requests = ModelRequest.parse(self._make_parse_content(encoding_scheme="v2"))
        assert requests[0].cond_vec is None

    def test_parse_raises_without_image(self):
        content = self._make_parse_content()
        del content[RequestField.IMAGE.value]
        with pytest.raises(ValueError, match="image"):
            ModelRequest.parse(content)
