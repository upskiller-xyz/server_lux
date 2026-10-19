"""Tests for the image converters' unit-range (0..1) → 0..255 scaling.

The expected values are what numpy 1.x produced for ``(data * 255).astype(np.uint8)``;
the converters must keep producing them under numpy 2 (NEP 50 promotion rules).
"""

import io
import zipfile

import cv2
import numpy as np

from src.server.services.remote.image_converters import (
    EncoderOutputConverter,
    ImageDataConverter,
    UnitRangeScaler,
)


def _decode_png(png_bytes: bytes) -> np.ndarray:
    return cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_UNCHANGED)


def _encoder_zip(image: np.ndarray) -> bytes:
    npy = io.BytesIO()
    np.save(npy, image)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("image.npy", npy.getvalue())
    return archive.getvalue()


def test_scale_upcasts_int8_like_numpy_1():
    # Arrange
    data = np.array([[-1, 0], [1, 0]], dtype=np.int8)

    # Act
    scaled = UnitRangeScaler.scale(data)

    # Assert
    assert scaled.dtype == np.int16
    assert scaled.tolist() == [[-255, 0], [255, 0]]


def test_scale_keeps_float32_dtype_and_values():
    # Arrange
    data = np.array([0.0, 0.5, 1.0, 1 / 255], dtype=np.float32)

    # Act
    scaled = UnitRangeScaler.scale(data)

    # Assert
    assert scaled.dtype == np.float32
    assert np.array_equal(scaled, data * np.float32(255))


def test_image_data_converter_encodes_int8_unit_range():
    # Arrange
    data = np.array([[-1, 0], [1, 0]], dtype=np.int8)

    # Act
    png_bytes = ImageDataConverter.to_bytes(data)

    # Assert
    assert _decode_png(png_bytes).tolist() == [[1, 0], [255, 0]]


def test_encoder_output_converter_encodes_int8_unit_range():
    # Arrange
    zip_bytes = _encoder_zip(np.array([[-1, 0], [1, 0]], dtype=np.int8))

    # Act
    png_bytes = EncoderOutputConverter.convert_to_png(zip_bytes)

    # Assert
    assert _decode_png(png_bytes).tolist() == [[1, 0], [255, 0]]
