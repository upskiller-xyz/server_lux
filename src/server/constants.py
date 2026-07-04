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
    ``HOST_SUFFIX`` (Scaleway serverless container/function endpoints live under
    ``*.scw.cloud``). A private endpoint requires a token read from ``TOKEN_ENV``,
    sent in the Scaleway auth header. Override the suffix if the region/domain
    differs.
    """
    HOST_SUFFIX: str = ".scw.cloud"
    TOKEN_ENV: str = "SCW_CONTAINER_TOKEN"
