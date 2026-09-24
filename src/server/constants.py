"""Application-wide constants

Single source of truth for magic numbers and configuration values.
Follows DRY principle - define once, reference everywhere.
"""


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

    @staticmethod
    def token_env(service_name: str) -> str:
        """Env var holding a service's Scaleway token, e.g. ``OBSTRUCTION_TOKEN``.

        Keyed by service so distinct Scaleway containers can each hold their own
        token; takes the service name value (a str) rather than the enum to keep
        this constants module free of enum imports and dependency-light.
        """
        return f"{service_name.upper()}{ScalewayBackend.TOKEN_ENV_SUFFIX}"


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
