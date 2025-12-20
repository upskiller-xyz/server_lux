from typing import Any, Dict, List, Callable
import numpy as np
import cv2
from PIL import Image
from io import BytesIO
import zipfile

from ...enums import ImageChannels
import logging
logger = logging.getLogger('logger')

class ImageDataConverter:
    """Converts different image data types to bytes using Adapter-Map pattern

    Uses cv2 for efficient image operations.
    Eliminates type checking if-else chains.
    Follows Single Responsibility Principle - only converts image data types.
    """

    @staticmethod
    def _from_numpy(data: np.ndarray) -> bytes:
        """Convert numpy array to PNG bytes

        Args:
            data: Numpy array
            logger: Logger instance

        Returns:
            PNG bytes
        """
        # Ensure uint8 format
        if data.dtype != np.uint8:
            if data.max() <= 1.0:
                data = (data * 255).astype(np.uint8)
            else:
                data = data.astype(np.uint8)

        # Encode to PNG using cv2
        success, buffer = cv2.imencode('.png', data)
        if not success:
            raise ValueError("Failed to encode numpy array to PNG")

        return buffer.tobytes()

    @staticmethod
    def _from_pil(data: Image.Image) -> bytes:
        """Convert PIL Image to PNG bytes

        Args:
            data: PIL Image
            logger: Logger instance

        Returns:
            PNG bytes
        """
        buffer = BytesIO()
        data.save(buffer, format='PNG')
        return buffer.getvalue()

    @staticmethod
    def _from_bytes(data: bytes) -> bytes:
        """Return bytes as-is

        Args:
            data: Bytes data
            logger: Logger instance

        Returns:
            Bytes data unchanged
        """
        return data

    # Map: Type check function -> Converter function
    CONVERTER_MAP: List[tuple] = [
        (lambda x: isinstance(x, np.ndarray), _from_numpy),
        (lambda x: isinstance(x, Image.Image), _from_pil),
        (lambda x: isinstance(x, bytes), _from_bytes),
    ]

    @classmethod
    def to_bytes(cls, image_data: Any) -> bytes:
        """Convert image data to bytes using adapter-map pattern

        Args:
            image_data: Image data (numpy array, PIL Image, or bytes)
            logger: Logger instance

        Returns:
            PNG image as bytes

        Raises:
            ValueError: If unsupported data type
        """
        for type_check, converter in cls.CONVERTER_MAP:
            if type_check(image_data):
                return converter(image_data)

        raise ValueError(
            f"Unsupported image_data type: {type(image_data)}. "
            f"Expected numpy.ndarray, PIL.Image, or bytes."
        )

class EncoderOutputConverter:
    """Converts encoder service output (ZIP with NPY) to PNG bytes

    The encoder service returns a ZIP file containing image.npy.
    This converter extracts the numpy array and converts it to PNG.
    Follows Single Responsibility Principle - only converts encoder output format.
    """

    @staticmethod
    def convert_to_png(zip_bytes: bytes) -> bytes:
        """Convert ZIP/NPY encoder output to PNG bytes

        Args:
            zip_bytes: ZIP file bytes containing image.npy

        Returns:
            PNG image as bytes

        Raises:
            ValueError: If conversion fails
        """
        try:
            # Extract numpy array from ZIP
            zip_buffer = BytesIO(zip_bytes)
            with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
                with zip_file.open('image.npy') as npy_file:
                    image_array = np.load(npy_file)
                    logger.info(f"Loaded encoder output: shape={image_array.shape}, dtype={image_array.dtype}")

                    # Normalize if needed (convert to 0-255 uint8 range)
                    if image_array.max() <= 1.0:
                        image_array = (image_array * 255).astype(np.uint8)
                    else:
                        image_array = image_array.astype(np.uint8)

                    # Convert to PNG using cv2
                    success, buffer = cv2.imencode('.png', image_array)
                    if not success:
                        raise ValueError("Failed to encode array to PNG")

                    png_bytes = buffer.tobytes()
                    logger.info(f"Converted encoder output to PNG: {len(png_bytes)} bytes")
                    return png_bytes

        except Exception as e:
            logger.error(f"Failed to convert encoder output to PNG: {e}")
            raise ValueError(f"Failed to convert encoder output: {e}")
