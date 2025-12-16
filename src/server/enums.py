from enum import Enum
from typing import Optional

from src.utils.extended_enum import ExtendedEnum


class ModelStatus(Enum):
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"


class ServerStatus(Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"

class DeploymentMode(Enum):
    """Deployment mode configuration"""
    LOCAL = "local"
    PRODUCTION = "production"


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


class ResponseStatus(Enum):
    """Status values for API responses"""
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


class HTTPHeader(Enum):
    """HTTP header field names"""
    CONTENT_TYPE = "Content-Type"
    AUTHORIZATION = "Authorization"
    ACCEPT = "Accept"


class HTTPContentType(Enum):
    """HTTP Content-Type values"""
    JSON = "application/json"
    FORM_DATA = "multipart/form-data"
    TEXT_PLAIN = "text/plain"


class ResponseKey(Enum):
    """Common keys used in API responses"""
    STATUS = "status"
    ERROR = "error"
    ERROR_TYPE = "error_type"
    DATA = "data"
    RESULT = "result"
    RESULTS = "results"
    MESSAGE = "message"
    WINDOW_NAME = "window_name"
    WINDOW_RESULTS = "window_results"
    PARTIAL_RESULTS = "partial_results"
    MERGED_RESULT = "merged_result"
    MERGER_ERROR = "merger_error"
    HORIZON_ANGLES = "horizon_angles"
    ZENITH_ANGLES = "zenith_angles"
    HORIZON_ANGLE = "horizon_angle"
    ZENITH_ANGLE = "zenith_angle"
    DIRECTION_ANGLE = "direction_angle"
    DIRECTION_ANGLES = "direction_angles"
    HORIZON = "horizon"
    ZENITH = "zenith"
    OBSTRUCTION_ANGLE_DEGREES = "obstruction_angle_degrees"
    HIGHEST_POINT = "highest_point"
    PREDICTION = "prediction"
    AUTHORIZATION_ERROR = "authorization_error"
    CONNECTION_ERROR = "connection_error"
    TIMEOUT_ERROR = "timeout_error"
    RESPONSE_ERROR = "response_error"
    SUCCESS = "success"


class EndpointType(ExtendedEnum):
    
    SIMULATE = "simulate"  # Renamed from GET_DF for clarity
    STATUS = "status"
    GET_STATS = "get_stats"
    GET_DF_RGB = "get_df_rgb"
    HORIZON_ANGLE = "horizon_angle"
    ZENITH_ANGLE = "zenith_angle"
    OBSTRUCTION = "obstruction"
    OBSTRUCTION_ALL = "obstruction_all"
    OBSTRUCTION_MULTI = "obstruction_multi"
    OBSTRUCTION_PARALLEL = "obstruction_parallel"
    ENCODE = "encode"
    ENCODE_RAW = "encode_raw"
    RUN = "run"
    CALCULATE_DIRECTION = "calculate-direction"
    MERGE = "merge"
    STATS_CALCULATE = "calculate"


class ServicePort(Enum):
    """Service port numbers"""
    
    OBSTRUCTION = 8081
    ENCODER = 8082
    MODEL = 8083
    MERGER = 8084
    STATS = 8085
    MAIN_SERVER = 8080


class ServiceHost(Enum):
    """Service hostnames"""
    LOCALHOST = "localhost"
    PRODUCTION_SERVER = "51.15.197.220"


class ErrorType(Enum):
    """Error type identifiers for error responses"""
    MISSING_AUTHORIZATION = "missing_authorization"
    INVALID_AUTH_FORMAT = "invalid_auth_format"
    INVALID_TOKEN = "invalid_token"
    MISSING_JSON = "missing_json"
    MISSING_FILE = "missing_file"
    VALIDATION_ERROR = "validation_error"
    INTERNAL_ERROR = "internal_error"


class ErrorMessage(Enum):
    """Standard error messages using Enumerator pattern"""
    MISSING_AUTHORIZATION = "Missing Authorization header"
    INVALID_AUTH_FORMAT = "Invalid Authorization header format. Expected: 'Bearer <token>'"
    INVALID_TOKEN = "Invalid authentication token"
    MISSING_JSON = "No JSON data provided"
    MISSING_FILE = "No file provided in request"


class NPZKey(Enum):
    """NPZ file key patterns for encoder responses"""
    IMAGE = "image"
    MASK = "mask"
    IMAGE_SUFFIX = "_image"
    MASK_SUFFIX = "_mask"


class RequestField(Enum):
    """Request field names for API requests using Enumerator pattern

    Eliminates magic strings in request construction across all services.
    """
    # Common fields
    DATA = "data"
    COLORSCALE = "colorscale"
    PARAMETERS = "parameters"
    MODEL_TYPE = "model_type"

    # Coordinate fields
    X = "x"
    Y = "y"
    Z = "z"
    X1 = "x1"
    Y1 = "y1"
    Z1 = "z1"
    X2 = "x2"
    Y2 = "y2"
    Z2 = "z2"

    # Obstruction fields
    
    MESH = "mesh"
    DIRECTION_ANGLE = "direction_angle"
    START_ANGLE = "start_angle"
    END_ANGLE = "end_angle"
    NUM_DIRECTIONS = "num_directions"
    OBSTRUCTION_ANGLE_HORIZON = "obstruction_angle_horizon"
    OBSTRUCTION_ANGLE_ZENITH = "obstruction_angle_zenith"

    # Window and room fields
    WINDOWS = "windows"
    ROOM_POLYGON = "room_polygon"
    WINDOW_NAME = "window_name"
    WINDOW_FRAME_RATIO = "window_frame_ratio"

    # Simulation fields
    RESULTS = "results"
    SIMULATIONS = "simulations"
    DF_VALUES = "df_values"
    DF_MATRIX = "df_matrix"
    ROOM_MASK = "room_mask"
    MASK = "mask"

    # Image fields
    FILE = "file"
    IMAGE_BASE64 = "image_base64"
    IMAGE_ARRAY = "image_array"
    INVERT_CHANNELS = "invert_channels"

    ROOF_HEIGHT = "height_roof_over_floor"
    FLOOR_HEIGHT = "floor_height_above_terrain"

    # Optimization flags
    USE_EARLY_EXIT_OPTIMIZATION = "use_early_exit_optimization"


class ImageMode(Enum):
    """Image mode identifiers for PIL Image"""
    RGB = "RGB"
    RGBA = "RGBA"
    L = "L"  # Grayscale
    LA = "LA"  # Grayscale with alpha


class InputDataType(Enum):
    """Input data type identifiers for type checking"""
    NUMPY_ARRAY = "numpy_array"
    PIL_IMAGE = "pil_image"
    BYTES = "bytes"


class ImageSize(Enum):
    """Standard image sizes used in the application"""
    TARGET_WIDTH = 128
    TARGET_HEIGHT = 128

    @property
    def as_tuple(self) -> tuple[int, int]:
        """Get image size as (width, height) tuple"""
        return (ImageSize.TARGET_WIDTH.value, ImageSize.TARGET_HEIGHT.value)


class ObstructionCalculationDefaults(Enum):
    """Default values for obstruction angle calculations"""
    START_ANGLE = 17.5  # degrees in half-circle coordinate system
    END_ANGLE = 162.5   # degrees in half-circle coordinate system
    NUM_DIRECTIONS = 64  # number of directions to calculate


class ImageChannels(Enum):
    """Number of channels in images"""
    GRAYSCALE = 1
    RGB = 3
    RGBA = 4


class ServiceName(Enum):
    """Service name identifiers for configuration lookup"""
    COLORMANAGE = "colormanage"
    OBSTRUCTION = "obstruction"
    ENCODER = "encoder"
    MODEL = "model"
    MERGER = "merger"
    STATS = "stats"

