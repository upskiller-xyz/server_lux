from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import numpy as np
import base64
import logging

from .base_contracts import RemoteServiceRequest, StandardResponse
from ....enums import RequestField, ResponseKey

logger = logging.getLogger('logger')


@dataclass
class ModelRequest(RemoteServiceRequest):
    """Request for model inference (simulation)

    Expects image data from encoder service in the image field.
    """
    image: bytes  # Binary image data from encoder
    filename: str = "image.png"
    invert_channels: bool = False

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> List['ModelRequest']:
        """Parse dictionary into ModelRequest

        Args:
            content: Dictionary with 'image' field containing binary image data

        Returns:
            List with single ModelRequest instance
        """
        image_data = content.get(RequestField.IMAGE.value)
        if not image_data:
            raise ValueError("Missing 'image' field in request data for ModelService")

        return [cls(
            image=image_data,
            filename=content.get('filename', 'image.png')
        )]

    @property
    def to_dict(self) -> Dict[str, Any]:
        # Model service doesn't use to_dict, it uploads multipart
        return {
            RequestField.IMAGE.value: self.image,
            'filename': self.filename
        }


@dataclass
class ModelResponse(StandardResponse):
    """Response from model/simulation service

    Used for /simulate, /get_df, and related endpoints.
    """
    content: np.ndarray
    shape: Optional[List[int]] = None
    mask: Optional[np.ndarray] = None

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> 'ModelResponse':
        """Parse response data from model service

        Returns ModelResponse instance with parsed content.
        """
        logger.info(f"[ModelResponse.parse] Parsing content keys: {list(content.keys())}")

        # Model service returns 'simulation' key
        raw_content = content.get(RequestField.SIMULATION.value)
        shape = content.get(RequestField.SHAPE.value)
        raw_mask = content.get(RequestField.MASK.value)

        logger.info(f"[ModelResponse.parse] raw_content type: {type(raw_content)}, shape: {shape}")
        if isinstance(raw_content, list) and len(raw_content) > 0:
            logger.info(f"[ModelResponse.parse] raw_content is list with {len(raw_content)} items, first item type: {type(raw_content[0])}")

        result_array = cls._parse_simulation(raw_content, shape)
        mask_array = cls._parse_mask(raw_mask)

        logger.info(f"[ModelResponse.parse] result_array shape: {result_array.shape if result_array is not None else 'None'}")

        return cls(
            content=result_array if result_array is not None else np.array([]),
            shape=list(result_array.shape) if result_array is not None else None,
            mask=mask_array
        )

    @classmethod
    def _parse_simulation(cls, raw_content: Any, shape: list[int] | None = None):
        if isinstance(raw_content, str):
            content_bytes = base64.b64decode(raw_content)
            result_array = np.frombuffer(content_bytes, dtype=np.float32)
            if shape:
                return result_array.reshape(shape)
        elif isinstance(raw_content, (list, np.ndarray)):
            return np.array(raw_content, dtype=np.float32)
        else:
            return np.array([])

    @classmethod
    def _parse_mask(cls, raw_mask: Any, shape: list[int] | None = None):
        mask_array = None
        if raw_mask is not None:
            if isinstance(raw_mask, str):
                mask_bytes = base64.b64decode(raw_mask)
                mask_array = np.frombuffer(mask_bytes, dtype=np.float32)
                if shape:
                    mask_array = mask_array.reshape(shape)
                return mask_array
            elif isinstance(raw_mask, (list, np.ndarray)):
                return np.array(raw_mask, dtype=np.float32)

    @property
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for orchestration flow"""
        result = {
            RequestField.SIMULATION.value: self.content.tolist() if self.content is not None else [],
            ResponseKey.STATUS.value: ResponseKey.SUCCESS.value
        }
        if self.mask is not None:
            result[RequestField.MASK.value] = self.mask.tolist()
        return result
