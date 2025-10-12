from enum import Enum


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
    GET_DF = "get_df"
    GET_STATS = "get_stats"
    GET_DF_RGB = "get_df_rgb"


class ServiceURL(Enum):
    COLORMANAGE = "https://colormanage-server-jia3y72oka-ma.a.run.app"
    DAYLIGHT = "https://daylight-processing-jia3y72oka-ma.a.run.app"
    DF_EVAL = "https://df-eval-server-jia3y72oka-ma.a.run.app"