"""Application-wide constants

Single source of truth for magic numbers and configuration values.
Follows DRY principle - define once, reference everywhere.
"""


class ImageConversionError:
    """Templates for the image-conversion failures raised by the converters."""
    UNSUPPORTED_TYPE: str = (
        "Unsupported image_data type: {actual}. "
        "Expected numpy.ndarray, PIL.Image, or bytes."
    )
    CONVERSION_FAILED: str = "Failed to convert encoder output: {error}"
    NO_NPZ_KEYS: str = "Could not find image/mask keys in NPZ. Available keys: {keys}"


class MergeError:
    """Templates for the inconsistencies detected while assembling the
    per-window data for the merge step."""
    NO_SIMULATION: str = "window '{window}' has no simulation result"
    NO_MASK: str = "window '{window}' has no mask"
    MASK_NOT_2D: str = "window '{window}' mask must be 2D, got {ndim}D with shape {shape}"
    NO_IMAGE_DATA: str = (
        "Encoder service did not return image data. Available keys: {keys}"
    )


class FieldPathBuilder:
    """Builds the dotted path naming a nested request field
    (``parameters`` + ``windows`` → ``parameters.windows``)."""
    SEPARATOR: str = "."

    @classmethod
    def nested(cls, *segments: str) -> str:
        return cls.SEPARATOR.join(segments)


class WindowNameBuilder:
    """Builds the positional window names used when a request lists windows
    without naming them (``window_0``, ``window_1``, …)."""
    TEMPLATE: str = "window_{index}"

    @classmethod
    def positional(cls, index: int) -> str:
        return cls.TEMPLATE.format(index=index)


class QuotaKeyBuilder:
    """Builds the Redis keys for the rolling-window quota counter and the
    identity they are keyed on."""
    KEY_TEMPLATE: str = "{prefix}:{identity}"
    BUCKET_TEMPLATE: str = "{bucket}:{identity}"
    SUBJECT_TEMPLATE: str = "sub:{subject}"
    IP_TEMPLATE: str = "ip:{address}"

    @classmethod
    def key(cls, prefix: str, identity: str) -> str:
        return cls.KEY_TEMPLATE.format(prefix=prefix, identity=identity)

    @classmethod
    def bucketed(cls, bucket: str, identity: str) -> str:
        """Separates the prediction bucket from the auxiliary one."""
        return cls.BUCKET_TEMPLATE.format(bucket=bucket, identity=identity)

    @classmethod
    def subject(cls, subject: str) -> str:
        return cls.SUBJECT_TEMPLATE.format(subject=subject)

    @classmethod
    def ip(cls, address: str) -> str:
        return cls.IP_TEMPLATE.format(address=address)


class ServiceUrlBuilder:
    """Builds the outbound URL for a remote service call."""
    TEMPLATE: str = "{base_url}/{endpoint}"
    PATH_TEMPLATE: str = "{base_url}{path}"

    @classmethod
    def endpoint(cls, base_url: str, endpoint_value: str) -> str:
        return cls.TEMPLATE.format(base_url=base_url, endpoint=endpoint_value)

    @classmethod
    def with_path(cls, base_url: str, path: str) -> str:
        """For a path that already carries its own leading slash."""
        return cls.PATH_TEMPLATE.format(base_url=base_url, path=path)


class EndpointPathBuilder:
    """Builds the leading-slash endpoint path used in outbound calls and in the
    service-error reports (``obstruction`` → ``/obstruction``)."""
    TEMPLATE: str = "/{endpoint}"

    @classmethod
    def path(cls, endpoint_value: str) -> str:
        return cls.TEMPLATE.format(endpoint=endpoint_value)


class ObstructionLogTemplate:
    """Log-line templates for the obstruction calculators."""
    DIRECTION_ERROR: str = "{message} (direction: {direction:.1f}\u00b0)"
    PARALLEL_COMPLETED: str = "Completed {count} calculations in {seconds:.2f}s"
    SINGLE_COMPLETED: str = "Completed obstruction calculation in {seconds:.2f}s"
    UNKNOWN_FORMAT: str = "Unknown response format! Keys: {keys}"
    EMPTY_ANGLES: str = "Empty angle arrays! Response keys: {keys}"
    DIRECTION_FAILED: str = "Failed to calculate obstruction for direction {index}: {error}"
    SERVICE_ERROR: str = "Obstruction service error: {error}"


class AuthHeaderBuilder:
    """Builds and parses the ``Authorization: Bearer <token>`` header.

    One place for the scheme, so the senders and the validators cannot drift
    apart on spelling or case handling.
    """
    SCHEME: str = "Bearer"
    TEMPLATE: str = "{scheme} {token}"
    EXPECTED_PARTS: int = 2

    @classmethod
    def bearer(cls, token: str) -> str:
        """``"abc"`` → ``"Bearer abc"``."""
        return cls.TEMPLATE.format(scheme=cls.SCHEME, token=token)

    @classmethod
    def extract_token(cls, auth_header: str) -> str:
        """Token out of a ``Bearer`` header, or an empty string if malformed.

        The scheme is matched case-insensitively, as HTTP requires.
        """
        parts = auth_header.split()
        if len(parts) != cls.EXPECTED_PARTS:
            return ""
        if parts[0].lower() != cls.SCHEME.lower():
            return ""
        return parts[1]


class ObstructionConcurrency:
    """Backpressure for calls to the obstruction service.

    The per-window fan-out is otherwise unbounded (default ThreadPoolExecutor),
    so a single burst of rooms can flood the obstruction backend far beyond its
    capacity. This caps concurrent in-flight obstruction requests per lux process
    to match the backend's ceiling (e.g. Scaleway serverless max-instances);
    excess callers queue on the semaphore instead of overwhelming the backend.
    """
    MAX_ENV: str = "OBSTRUCTION_MAX_CONCURRENCY"
    DEFAULT_MAX: int = 10


class ObstructionAngleDefaults:
    """Default values for obstruction angle calculations

    Used across all obstruction calculation services and orchestrators.
    """
    START_ANGLE_DEGREES: float = 17.5
    END_ANGLE_DEGREES: float = 162.5
    NUM_DIRECTIONS: int = 64
    TIMEOUT_SECONDS: int = 300
    EXPECTED_ANGLE_COUNT: int = 64


class ObstructionRequestDefaults:
    """Defaults shared by the obstruction request contracts and service.

    ``WINDOW_NAME`` is the sentinel a single-window (non-orchestrated) request
    carries. ObstructionService returns flat angle lists for it and a
    ``{window_name: angles}`` mapping for every other name.
    """
    WINDOW_NAME: str = "window"
    UNOBSTRUCTED_ANGLE_DEGREES: float = 0.0


class ImageDefaults:
    """Default values for image processing"""
    TARGET_WIDTH: int = 128
    TARGET_HEIGHT: int = 128


class MeshValidation:
    """Mesh validation constants"""
    MIN_TRIANGLES: int = 0  # Empty mesh is allowed


class DeploymentMode:
    """Deployment mode constants"""
    ENV_VAR: str = "DEPLOYMENT_MODE"
    LOCAL: str = "local"
    PRODUCTION: str = "production"


class DefaultMaskValue:
    """Default mask value when creating masks"""
    FILL_VALUE: int = 1


class ModalBackend:
    """Constants for detecting and authenticating against Modal-hosted services.

    A remote service is treated as Modal-hosted when its URL host ends with
    ``HOST_SUFFIX``; outgoing calls then carry proxy-auth headers read from the
    credential environment variables below.
    """
    HOST_SUFFIX: str = ".modal.run"
    KEY_ENV: str = "MODAL_KEY"
    SECRET_ENV: str = "MODAL_SECRET"


class ScalewayBackend:
    """Constants for detecting and authenticating against Scaleway serverless.

    A remote service is treated as Scaleway-hosted when its URL host ends with
    ``HOST_SUFFIX``. All Scaleway serverless container/function endpoints live
    under ``*.scw.cloud`` regardless of region, so the single suffix covers every
    region. A private endpoint requires a token sent in the Scaleway auth header;
    the token is read from a per-service environment variable so each Scaleway
    container can carry its own credential (e.g. ``OBSTRUCTION_TOKEN``).
    """
    HOST_SUFFIX: str = ".scw.cloud"
    TOKEN_ENV_SUFFIX: str = "_TOKEN"
    TOKEN_ENV_TEMPLATE: str = "{service}{suffix}"

    @staticmethod
    def token_env(service_name: str) -> str:
        """Env var holding a service's Scaleway token, e.g. ``OBSTRUCTION_TOKEN``.

        Keyed by service so distinct Scaleway containers can each hold their own
        token; takes the service name value (a str) rather than the enum to keep
        this constants module free of enum imports and dependency-light.
        """
        return ScalewayBackend.TOKEN_ENV_TEMPLATE.format(
            service=service_name.upper(), suffix=ScalewayBackend.TOKEN_ENV_SUFFIX
        )


class CorsPolicy:
    """CORS preflight policy for the public API.

    Every browser call carries an ``Authorization`` header, so none of them are
    CORS-simple: each one is preceded by its own ``OPTIONS`` preflight. Without an
    explicit ``Access-Control-Max-Age`` browsers fall back to a ~5 s preflight
    cache, which doubles the request count the gateway sees and drains its rate
    limiter during the per-window fan-out. Caching the preflight for a day means a
    client pays for it once per session instead of once per call.

    Chromium caps the honoured value at 2 hours, Firefox at 24 hours; sending the
    larger value is safe — each browser clamps it to its own ceiling.
    """
    MAX_AGE_SECONDS: int = 86400
