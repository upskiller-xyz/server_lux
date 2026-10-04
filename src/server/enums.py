from enum import Enum

from src.utils.extended_enum import ExtendedEnumMixin


class Methods(Enum):
    GET = "GET"
    POST = "POST"

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
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    TOO_MANY_REQUESTS = 429
    INTERNAL_SERVER_ERROR = 500
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504


class ResponseStatus(Enum):
    """Status values for API responses"""
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


class TrialStatus(Enum):
    """Trial status values reported by ``GET /v1/trial/status``.

    Part of the API contract with the Revit plugin, so the values are enumed
    rather than inlined at the call site.
    """
    NOT_APPLICABLE = "not_applicable"  # caller is not the trial client
    NOT_STARTED = "not_started"        # no guarded request made yet
    ACTIVE = "active"
    EXPIRED = "expired"


class TokenClaim(Enum):
    """JWT claim names read off a validated Auth0 token.

    ``TRIAL_DOMAIN`` is the namespace-qualified custom claim the trial login
    Action stamps with the caller's email domain (e.g. "foretagx.se"); the
    trial guard keys the company-wide trial clock on its value.
    """
    SUBJECT = "sub"
    AUTHORIZED_PARTY = "azp"
    EXPIRES_AT = "exp"
    ISSUER = "iss"
    AUDIENCE = "aud"
    TRIAL_DOMAIN = "https://upskiller/trial_domain"


class ApiVersion(Enum):
    """URL version prefix for the public API. Independent of the package
    version — a patch release must not move the routes."""
    V1 = "v1"


class AuthContextKey(Enum):
    """``flask.g`` attribute names the authenticator populates from a validated
    token. Single source of truth for the claim-to-guard boundary: the auth
    strategy writes these, the rate limiter and the trial guard read them.
    """
    SUBJECT = "auth_subject"           # Auth0 `sub` (the end user)
    CLIENT_ID = "auth_client_id"       # Auth0 `azp` (authorized party = client id)
    DOMAIN = "auth_domain"             # custom trial-domain claim (the company)


class HTTPHeader(Enum):
    """HTTP header field names"""
    CONTENT_TYPE = "Content-Type"
    AUTHORIZATION = "Authorization"
    ACCEPT = "Accept"
    # Caller-identity headers (telemetry): who's calling, which plugin build,
    # and which host application it's embedded in.
    CLIENT_NAME = "X-Client-Name"
    CLIENT_VERSION = "X-Client-Version"
    HOST_VERSION = "X-Host-Version"
    # Trial headers (responses): when the caller's company-wide trial window
    # started and when it ends. ISO-8601 UTC.
    TRIAL_STARTED_AT = "X-Trial-Started-At"
    TRIAL_EXPIRES_AT = "X-Trial-Expires-At"


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
    LIMIT = "limit"
    REMAINING = "remaining"
    RESET_AT = "reset_at"
    TRIAL_STARTED_AT = "trial_started_at"
    TRIAL_EXPIRES_AT = "trial_expires_at"
    REMAINING_HOURS = "remaining_hours"
    WINDOW_NAME = "window_name"
    WINDOW_RESULTS = "window_results"
    PARTIAL_RESULTS = "partial_results"
    MERGED_RESULT = "merged_result"
    MERGER_ERROR = "merger_error"
    DIRECTION_ANGLE = "direction_angle"
    DIRECTION_ANGLES = "direction_angles"
    DIRECTION_ANGLES_DEGREES = "direction_angles_degrees"
    HORIZON = "horizon"
    ZENITH = "zenith"
    OBSTRUCTION_ANGLE_DEGREES = "obstruction_angle_degrees"
    HIGHEST_POINT = "highest_point"
    AUTHORIZATION_ERROR = "authorization_error"
    CONNECTION_ERROR = "connection_error"
    TIMEOUT_ERROR = "timeout_error"
    RESPONSE_ERROR = "response_error"
    SUCCESS = "success"


class EndpointType(ExtendedEnumMixin, Enum):
    
    SIMULATE = "simulate"  # Renamed from GET_DF for clarity
    STATUS = "status"
    GET_STATS = "get_stats"
    GET_DF_RGB = "get_df_rgb"
    HORIZON = "horizon"
    ZENITH = "zenith"
    OBSTRUCTION = "obstruction"
    OBSTRUCTION_ALL = "obstruction_all"
    OBSTRUCTION_MULTI = "obstruction_multi"
    OBSTRUCTION_PARALLEL = "obstruction_parallel"
    ENCODE = "encode"
    ENCODE_RAW = "encode_raw"
    RUN = "run"
    RUN_DETAILED = "run_detailed"
    CALCULATE_DIRECTION = "calculate-direction"
    REFERENCE_POINT = "get-reference-point"
    EXTERNAL_REFERENCE_POINT = "get-external-reference-point"
    MERGE = "merge"
    STATS_CALCULATE = "calculate"
    MODEL_SPEC = "spec"
    TRIAL_STATUS = "trial_status"


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
    LOCALHOST = "http://localhost"
    PRODUCTION_SERVER = "http://51.15.197.220"


class AuthType(ExtendedEnumMixin, Enum):
    """Authentication type identifiers"""
    TOKEN = "token"
    AUTH0 = "auth0"
    NONE = "none"


class JwtAlgorithm(Enum):
    """Asymmetric JWT signing algorithms accepted for JWKS-verified tokens.

    Symmetric (HS*) algorithms are deliberately excluded: a JWKS publishes
    public keys, and accepting HS* would let a public key act as an HMAC secret.
    """
    RS256 = "RS256"
    RS384 = "RS384"
    RS512 = "RS512"
    ES256 = "ES256"
    ES384 = "ES384"
    ES512 = "ES512"
    PS256 = "PS256"
    PS384 = "PS384"
    PS512 = "PS512"


class ErrorType(Enum):
    """Error type identifiers for error responses"""
    MISSING_AUTHORIZATION = "missing_authorization"
    INVALID_AUTH_FORMAT = "invalid_auth_format"
    INVALID_TOKEN = "invalid_token"
    INVALID_JWT = "invalid_jwt"
    EXPIRED_JWT = "expired_jwt"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    TRIAL_EXPIRED = "trial_expired"
    TRIAL_DOMAIN_MISSING = "trial_domain_missing"
    TRIAL_STORE_UNAVAILABLE = "trial_store_unavailable"
    MISSING_JSON = "missing_json"
    MISSING_FILE = "missing_file"
    VALIDATION_ERROR = "validation_error"
    INTERNAL_ERROR = "internal_error"


class ValidationMessage(Enum):
    """Templates for the field-validation messages returned to callers.

    Shared so the same defect reads identically wherever it is detected
    (request parsing, contract parsing, parameter validation).
    """
    MISSING_FIELD = "Missing required field: {field}"
    MISSING_NAMED_FIELD = "Required field '{field}' is missing"
    MUST_BE_DICT = "Field '{field}' must be a dictionary"
    MUST_BE_LIST = "Field '{field}' must be a list"
    MUST_BE_MESH = "Field '{field}' must be a list, a split dict or a binary mesh payload"
    MUST_BE_TYPE = "{field} must be a {expected}"
    MUST_BE_NUMBER = "Field '{field}' must be a valid number, got {actual}"
    MISSING_IN_DATA = "Missing '{field}' field in request data"
    WINDOW_MISSING_FIELD = "Window '{window}' missing required field: {field}"


class LogMessage(Enum):
    """Fixed log-line texts, so the wording lives in one place rather than
    inline at the logging call."""
    AUTH_NONE = "Community Edition - No authentication required ✨"
    AUTH_TOKEN = "Token-based authentication enabled"
    AUTH_AUTH0 = "Auth0 JWT authentication enabled"
    AUTH_UNKNOWN = "Unknown authentication type"


class ErrorMessage(Enum):
    """Standard error messages using Enumerator pattern"""
    MISSING_AUTHORIZATION = "Missing Authorization header"
    INVALID_AUTH_FORMAT = "Invalid Authorization header format. Expected: 'Bearer <token>'"
    INVALID_TOKEN = "Invalid authentication token"
    INVALID_JWT = "Invalid JWT token"
    EXPIRED_JWT = "JWT token has expired"
    INSUFFICIENT_PERMISSIONS = "Insufficient permissions"
    RATE_LIMIT_EXCEEDED = "Request limit reached. Try again after the reset time."
    TRIAL_EXPIRED = "Your trial period has ended"
    TRIAL_DOMAIN_MISSING = "Your sign-in domain is not registered for this trial"
    TRIAL_STORE_UNAVAILABLE = "Trial service is temporarily unavailable. Try again later."
    MISSING_JSON = "No JSON data provided"
    MISSING_FILE = "No file provided in request"
    INTERNAL_ERROR = "Internal server error"
    UPSTREAM_ERROR = "{service} service error"
    UPSTREAM_UNAVAILABLE = "{service} service unavailable"
    UPSTREAM_TIMEOUT = "{service} service timeout"


class NPZKey(Enum):
    """NPZ file key patterns for encoder responses"""
    IMAGE = "image"
    MASK = "mask"
    IMAGE_SUFFIX = "image"
    MASK_SUFFIX = "mask"


class RequestField(Enum):
    """Request field names for API requests using Enumerator pattern

    Eliminates magic strings in request construction across all services.
    """
    # Common fields
    DATA = "data"
    COLORSCALE = "colorscale"
    PARAMETERS = "parameters"
    MODEL_TYPE = "model_type"
    MODEL_NAME = "model_name"

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
    HORIZON = "horizon"
    ZENITH = "zenith"

    # Window and room fields
    WINDOWS = "windows"
    ROOM_POLYGON = "room_polygon"
    WINDOW_NAME = "window_name"
    WINDOW_FRAME_RATIO = "window_frame_ratio"

    # Simulation fields
    RESULT = "result"
    IMAGE = "image"
    SIMULATION = "simulation"
    DF_MATRIX = "df_matrix"
    ROOM_MASK = "room_mask"
    DF_VALUES = "df_values"
    MASK = "mask"
    SHAPE = "shape"

    # Image fields
    MODEL = "model"
    FILE = "file"
    IMAGE_BASE64 = "image_base64"
    IMAGE_ARRAY = "image_array"
    INVERT_CHANNELS = "invert_channels"

    # Reference point
    REFERENCE_POINT = "reference_point"
    EXTERNAL_REFERENCE_POINT = "external_reference_point"

    ROOF_HEIGHT = "height_roof_over_floor"
    FLOOR_HEIGHT = "floor_height_above_terrain"

    # Optimization flags
    USE_EARLY_EXIT_OPTIMIZATION = "use_early_exit_optimization"

    # Model spec fields (resolved from spec.json before encoding)
    ENCODING_SCHEME = "encoding_scheme"
    ENCODER_MODEL_TYPE = "encoder_model_type"

    # Conditioning vector for models that require parameter injection
    COND_VEC = "cond_vec"


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


class ServiceBackend(ExtendedEnumMixin, Enum):
    """Backend hosting a remote service.

    Resolved from the service URL: a Modal-hosted endpoint requires proxy-auth
    headers, a private Scaleway serverless endpoint requires an auth token, a
    plain container endpoint requires none. The URL itself is the switch.
    """
    CONTAINER = "container"
    MODAL = "modal"
    SCALEWAY = "scaleway"


class ModalAuthHeader(Enum):
    """Modal proxy-auth header names.

    Modal web endpoints created with ``requires_proxy_auth=True`` expect a
    proxy-auth token sent as these two headers.
    """
    KEY = "Modal-Key"
    SECRET = "Modal-Secret"


class ScalewayAuthHeader(Enum):
    """Scaleway serverless auth header name.

    A private Scaleway serverless container/function is invoked with a generated
    token passed in this header; the platform gateway validates it before the
    request reaches the container.
    """
    TOKEN = "X-Auth-Token"

