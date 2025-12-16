from typing import Any, Dict, List, Callable
import numpy as np
import cv2
from PIL import Image
from io import BytesIO
from ...interfaces import ILogger
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
    def _from_numpy(data: np.ndarray, logger: ILogger) -> bytes:
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
    def _from_pil(data: Image.Image, logger: ILogger) -> bytes:
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
    def _from_bytes(data: bytes, logger: ILogger) -> bytes:
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
    def to_bytes(cls, image_data: Any, logger: ILogger) -> bytes:
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
                return converter(image_data, logger)

        raise ValueError(
            f"Unsupported image_data type: {type(image_data)}. "
            f"Expected numpy.ndarray, PIL.Image, or bytes."
        )


class ImageChannelInverter:
    """Handles image channel inversion using numpy slicing

    Uses numpy array slicing [:, :, ::-1] for efficient channel reversal.
    Checks number of channels instead of image mode strings.
    Follows Single Responsibility Principle - only inverts image channels.
    """

    @staticmethod
    def _invert_3_channels(img: np.ndarray) -> np.ndarray:
        """Invert 3-channel image (RGB -> BGR) using numpy slicing

        Args:
            img: 3-channel image array

        Returns:
            Channel-inverted image
        """
        return img[:, :, ::-1]

    @staticmethod
    def _invert_4_channels(img: np.ndarray) -> np.ndarray:
        """Invert 4-channel image (RGBA -> BGRA) using numpy slicing

        Reverses first 3 channels (RGB), keeps alpha channel in place.

        Args:
            img: 4-channel image array

        Returns:
            Channel-inverted image
        """
        result = img.copy()
        result[:, :, :3] = img[:, :, 2::-1]  # Reverse RGB channels
        return result

    @staticmethod
    def _no_inversion(img: np.ndarray) -> np.ndarray:
        """No inversion for 1, 2, or unsupported channel counts

        Args:
            img: Image array

        Returns:
            Unchanged image array
        """
        return img

    # Map: Channel count -> Inversion function
    INVERSION_MAP: Dict[int, Callable[[np.ndarray], np.ndarray]] = {
        ImageChannels.RGB.value: _invert_3_channels,
        ImageChannels.RGBA.value: _invert_4_channels,
    }

    @classmethod
    def invert(cls, image_bytes: bytes, logger: ILogger, invert: bool = True) -> bytes:
        """Invert image channels if requested using adapter-map pattern

        Args:
            image_bytes: Image data as bytes
            logger: Logger instance
            invert: If True, invert channels (default: True)

        Returns:
            Image bytes (inverted if requested)
        """
        if not invert:
            return image_bytes

        # Decode image using cv2
        img_array = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
        if img_array is None:
            logger.error("Failed to decode image bytes")
            return image_bytes

        # Get number of channels
        if len(img_array.shape) == 2:
            channels = 1  # Grayscale
        else:
            channels = img_array.shape[2]

        logger.info(f"Image has {channels} channel(s)")

        # Get inverter function from map
        inverter = cls.INVERSION_MAP.get(channels, cls._no_inversion)

        if inverter == cls._no_inversion:
            logger.warning(f"Image has {channels} channel(s), only 3 (RGB) and 4 (RGBA) are invertible. Skipping inversion.")
            return image_bytes

        # Invert channels
        img_inverted = inverter(img_array)
        logger.info(f"Inverted {channels}-channel image")

        # Encode back to PNG
        success, buffer = cv2.imencode('.png', img_inverted)
        if not success:
            logger.error("Failed to encode inverted image")
            return image_bytes

        return buffer.tobytes()
