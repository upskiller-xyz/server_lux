import logging
import time
import io
import numpy as np
from PIL import Image
from ...remote.contracts import EncoderResponse
from ....enums import RequestField, ResponseKey, NPZKey
from ...remote import EncoderService
from ...helpers.npz_key_extractor import NPZKeyExtractor
from .base_handler import ProcessingHandler, WindowContext


class EncodingHandler(ProcessingHandler):
    """Handles room encoding step

    Encodes room with obstruction angles.
    Updates context with encoded_image_bytes and mask_array.
    """

    def __init__(self, encoder_service: EncoderService):
        super().__init__()
        self._encoder = encoder_service

    def _process(self, context: WindowContext) -> dict:
        """Encode room parameters with obstruction angles"""
        start_time = time.time()
        self._logger.info(f"[{context.window_name}] ⏱️  Starting encoding at {time.time():.3f}")
        self._logger.info(f"[{context.window_name}] Encoding room with obstruction angles (direction_angle={context.direction_angle:.4f} rad)")

        # Build encoding parameters
        encoding_params = self._build_encoding_params(context)

        # Execute encoding
        encoded_bytes = self._encoder.encode(
            model_type=context.model_type,
            parameters=encoding_params
        )

        elapsed = time.time() - start_time
        self._logger.info(f"[{context.window_name}] ⏱️  Encoding completed in {elapsed:.2f}s, response size: {len(encoded_bytes)} bytes")

        # Parse encoding response (NPZ or PNG)
        parse_result = self._parse_encoded_response(encoded_bytes, context)
        if parse_result.get(ResponseKey.STATUS.value) != ResponseKey.SUCCESS.value:
            return parse_result

        return self._success()

    def _build_encoding_params(self, context: WindowContext) -> dict:
        """Build parameters for encoder service"""
        encoder_window_data = {
            RequestField.X1.value: context.x1,
            RequestField.Y1.value: context.y1,
            RequestField.Z1.value: context.z1,
            RequestField.X2.value: context.x2,
            RequestField.Y2.value: context.y2,
            RequestField.Z2.value: context.z2,
            RequestField.WINDOW_FRAME_RATIO.value: context.window_frame_ratio,
            RequestField.DIRECTION_ANGLE.value: context.direction_angle,
            RequestField.OBSTRUCTION_ANGLE_HORIZON.value: context.horizon_angles,
            RequestField.OBSTRUCTION_ANGLE_ZENITH.value: context.zenith_angles
        }

        return {
            RequestField.ROOM_POLYGON.value: context.room_polygon,
            RequestField.WINDOWS.value: {
                context.window_name: encoder_window_data
            }
        }

    def _parse_encoded_response(self, encoded_bytes: bytes, context: WindowContext) -> dict:
        """Parse encoder response (NPZ or PNG format)"""
        self._logger.info(f"[{context.window_name}] 🔍 First 8 bytes: {encoded_bytes[:8].hex() if len(encoded_bytes) >= 8 else 'N/A'}")

        # Check if NPZ format
        if self._is_npz_format(encoded_bytes):
            return self._parse_npz_response(encoded_bytes, context)

        # Check if PNG format
        if self._is_png_format(encoded_bytes):
            return self._parse_png_response(encoded_bytes, context)

        self._logger.warning(f"[{context.window_name}] ⚠️  Unknown encoder response format")
        context.encoded_image_bytes = encoded_bytes
        context.mask_array = None
        return self._success()

    def _is_npz_format(self, data: bytes) -> bool:
        """Check if data is NPZ format (ZIP signature)"""
        return data[:2] == b'PK'

    def _is_png_format(self, data: bytes) -> bool:
        """Check if data is PNG format"""
        return data[:8] == b'\x89PNG\r\n\x1a\n'

    def _parse_npz_response(self, encoded_bytes: bytes, context: WindowContext) -> dict:
        """Parse NPZ format response and create EncoderResponse object"""
        self._logger.info(f"[{context.window_name}] 📦 Detected NPZ format from encoder")

        try:
            # Parse NPZ using EncoderResponse
            encoder_response = EncoderResponse.parse(encoded_bytes)
            context.encoder_response = encoder_response

            self._logger.info(f"[{context.window_name}] Extracted image from NPZ: shape={encoder_response.image.shape}, dtype={encoder_response.image.dtype}")
            self._logger.info(f"[{context.window_name}] Extracted mask from NPZ: shape={encoder_response.mask.shape}")

            # Convert image array to PNG bytes for model service (legacy compatibility)
            context.encoded_image_bytes = self._convert_array_to_png(encoder_response.image, context.window_name)
            context.mask_array = encoder_response.mask

            return self._success()

        except Exception as e:
            return self._error(f"Failed to parse NPZ response: {str(e)}")

    def _parse_png_response(self, encoded_bytes: bytes, context: WindowContext) -> dict:
        """Parse PNG format response"""
        self._logger.info(f"[{context.window_name}] 🖼️  Detected PNG format from encoder (legacy format)")
        context.encoded_image_bytes = encoded_bytes
        context.mask_array = None
        return self._success()

    def _convert_array_to_png(self, image_array: np.ndarray, window_name: str) -> bytes:
        """Convert numpy array to PNG bytes"""
        # Ensure uint8 format
        if image_array.dtype != np.uint8:
            if image_array.max() <= 1.0:
                image_array = (image_array * 255).astype(np.uint8)
            else:
                image_array = image_array.astype(np.uint8)

        img = Image.fromarray(image_array)
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        png_bytes = buffer.getvalue()
        self._logger.info(f"[{window_name}] Converted NPZ image to PNG: {len(png_bytes)} bytes")
        return png_bytes
