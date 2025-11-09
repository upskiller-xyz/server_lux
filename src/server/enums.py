from enum import Enum
from typing import Optional


class ModelStatus(Enum):
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"


class ServerStatus(Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ContentType(Enum):
    IMAGE_JPEG = "image/jpeg"
    IMAGE_PNG = "image/png"
    IMAGE_WEBP = "image/webp"
    IMAGE_BMP = "image/bmp"

    @classmethod
    def is_image(cls, content_type: str) -> bool:
        return content_type.startswith('image/')


class HTTPStatus(Enum):
    OK = 200
    BAD_REQUEST = 400
    INTERNAL_SERVER_ERROR = 500


class EndpointType(Enum):
    TO_RGB = "to_rgb"
    TO_VALUES = "to_values"
    SIMULATE = "simulate"  # Renamed from GET_DF for clarity
    GET_DF = "get_df"  # Keep for backwards compatibility
    GET_STATS = "get_stats"
    GET_DF_RGB = "get_df_rgb"
    HORIZON_ANGLE = "horizon_angle"
    ZENITH_ANGLE = "zenith_angle"
    OBSTRUCTION = "obstruction"
    OBSTRUCTION_ALL = "obstruction_all"
    ENCODE = "encode"
    RUN = "run"
    POSTPROCESS = "postprocess"


class ServiceName(Enum):
    """Service name identifiers for configuration lookup"""
    COLORMANAGE = "colormanage"
    DAYLIGHT = "daylight"
    DF_EVAL = "df_eval"
    OBSTRUCTION = "obstruction"
    ENCODER = "encoder"
    POSTPROCESS = "postprocess"


class ServiceURL(Enum):
    """Service URL enum - dynamically resolved based on deployment mode"""
    COLORMANAGE = "colormanage"
    DAYLIGHT = "daylight"
    DF_EVAL = "df_eval"
    OBSTRUCTION = "obstruction"
    ENCODER = "encoder"
    POSTPROCESS = "postprocess"

    @property
    def value(self) -> str:
        """Get the actual URL based on deployment mode"""
        from .config import get_service_config
        config = get_service_config()
        return config.get_service_url(self._value_)