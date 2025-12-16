import time
import io
import numpy as np
from PIL import Image
from ....interfaces import ILogger
from ....enums import RequestField, ResponseKey, NPZKey
from ...remote import EncoderService
from ...helpers.npz_key_extractor import NPZKeyExtractor
from .base_handler import ProcessingHandler, WindowContext


class EncodingHandler(ProcessingHandler):
    """Handles room encoding step

    Encodes room with obstruction angles.
    Updates context with encoded_image_bytes and mask_array.
    """

    def __init__(self, encoder_service: EncoderService, logger: ILogger):
        super().__init__(logger)
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
        """Parse NPZ format response"""
        self._logger.info(f"[{context.window_name}] 📦 Detected NPZ format from encoder")

        npz_data = np.load(io.BytesIO(encoded_bytes))
        keys = list(npz_data.keys())
        self._logger.info(f"[{context.window_name}] NPZ keys: {keys}")

        # Extract image and mask keys
        image_key, mask_key = NPZKeyExtractor.extract_keys(context.window_name, keys)

        if not image_key:
            return self._error(f"No image found in encoder NPZ response. Available keys: {keys}")

        self._logger.info(f"[{context.window_name}] Using keys: image={image_key}, mask={mask_key}")

        # Extract image array
        image_array = npz_data[image_key]
        self._logger.info(f"[{context.window_name}] Extracted image from NPZ: shape={image_array.shape}, dtype={image_array.dtype}")

        # Extract mask if available
        if mask_key and mask_key in npz_data:
            context.mask_array = npz_data[mask_key]
            self._logger.info(f"[{context.window_name}] Extracted mask from NPZ: shape={context.mask_array.shape}")
        else:
            context.mask_array = None
            self._logger.warning(f"[{context.window_name}] No mask found in NPZ")

        # Convert numpy array to PNG bytes
        context.encoded_image_bytes = self._convert_array_to_png(image_array, context.window_name)

        return self._success()

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
