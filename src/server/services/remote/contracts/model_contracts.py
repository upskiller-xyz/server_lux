from dataclasses import dataclass, field
from typing import Callable, Dict, Any, List, Optional
import math
import numpy as np
import base64
import logging

from .base_contracts import RemoteServiceRequest, StandardResponse
from ....enums import RequestField, ResponseKey

logger = logging.getLogger('logger')


class CondVecBuilder:
    """Builds conditioning vector from request parameters based on encoding scheme.

    Uses Strategy Pattern — each encoding scheme maps to its own builder function.
    """

    @classmethod
    def build(cls, content: Dict[str, Any]) -> Optional[np.ndarray]:
        """Return cond_vec for the given content, or None if not required."""
        encoding_scheme = content.get(RequestField.ENCODING_SCHEME.value)
        builder = cls._SCHEME_BUILDERS.get(encoding_scheme)
        if builder is None:
            return None

        params = content.get(RequestField.PARAMETERS.value, {})
        windows = params.get(RequestField.WINDOWS.value, {})
        if not windows:
            return None

        window_id = next(iter(windows))
        win = windows[window_id]

        direction_angles = content.get(RequestField.DIRECTION_ANGLE.value, {})
        if isinstance(direction_angles, dict):
            dir_angle = float(direction_angles.get(window_id, 0.0))
        else:
            dir_angle = float(direction_angles or 0.0)

        return builder(params, win, dir_angle)

    @staticmethod
    def _build_v5(params: Dict[str, Any], win: Dict[str, Any], dir_angle: float) -> np.ndarray:
        height_roof = float(params.get(RequestField.ROOF_HEIGHT.value, 0.0))
        floor_height = float(params.get(RequestField.FLOOR_HEIGHT.value, 0.0))
        win_height = abs(
            float(win.get(RequestField.Z2.value, 0.0)) - float(win.get(RequestField.Z1.value, 0.0))
        )
        win_width = math.sqrt(
            (float(win.get(RequestField.X2.value, 0.0)) - float(win.get(RequestField.X1.value, 0.0))) ** 2 +
            (float(win.get(RequestField.Y2.value, 0.0)) - float(win.get(RequestField.Y1.value, 0.0))) ** 2
        )
        frame_ratio = float(win.get(RequestField.WINDOW_FRAME_RATIO.value, 0.2))
        return np.array([
            np.clip(height_roof, 0.0, 30.0) / 30.0,
            np.clip(floor_height, 0.0, 10.0) / 10.0,
            1.0 - np.clip((win_height - 0.2) / 4.8, 0.0, 1.0),
            np.clip(win_width, 0.5, 5.0) / 5.0,
            1.0 - np.clip(frame_ratio, 0.0, 1.0),
            np.clip(dir_angle, 0.0, 2 * math.pi) / (2 * math.pi),
        ], dtype=np.float32)

    # Strategy map: encoding scheme → cond_vec builder function
    _SCHEME_BUILDERS: Dict[str, Callable] = {}


CondVecBuilder._SCHEME_BUILDERS = {
    "v5": CondVecBuilder._build_v5,
}


@dataclass
class ModelRequest(RemoteServiceRequest):
    """Request for model inference (simulation)

    Expects image data from encoder service in the image field.
    """
    image: bytes  # Binary image data from encoder
    model_name: str = "df_default_2.0.1"
    filename: str = "image.png"
    cond_vec: Optional[np.ndarray] = field(default=None)

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

        model_name = content.get(RequestField.MODEL_NAME.value) or content.get(RequestField.MODEL_TYPE.value, "df_default_2.0.1")
        cond_vec = CondVecBuilder.build(content)
        if cond_vec is not None:
            logger.info("[ModelRequest] Built cond_vec (dim=%d) for encoding_scheme='%s'",
                        len(cond_vec), content.get(RequestField.ENCODING_SCHEME.value))
        return [cls(
            image=image_data,
            model_name=model_name,
            filename=content.get('filename', 'image.png'),
            cond_vec=cond_vec,
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
        # Model service returns 'simulation' key
        raw_content = content.get(RequestField.SIMULATION.value)
        shape = content.get(RequestField.SHAPE.value)
        raw_mask = content.get(RequestField.MASK.value)

        result_array = cls._parse_simulation(raw_content, shape)
        mask_array = cls._parse_mask(raw_mask)

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
