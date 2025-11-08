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


class ServiceURL(Enum):
    COLORMANAGE = "https://colormanage-server-182483330095.europe-north2.run.app"
    DAYLIGHT = "https://daylight-factor-182483330095.europe-north2.run.app"
    DF_EVAL = "https://df-eval-server-182483330095.europe-north2.run.app"
    OBSTRUCTION = "https://obstruction-server-182483330095.europe-north2.run.app"
    ENCODER = "https://encoder-server-182483330095.europe-north2.run.app"
    POSTPROCESS = "https://daylight-processing-182483330095.europe-north2.run.app"