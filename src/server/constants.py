"""Application-wide constants

Single source of truth for magic numbers and configuration values.
Follows DRY principle - define once, reference everywhere.
"""


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
