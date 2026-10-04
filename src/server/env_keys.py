from enum import Enum

from src.utils.extended_enum import ExtendedEnumMixin


class EnvKey(ExtendedEnumMixin, Enum):
    """Every environment variable the server reads, in one place.

    Configuration is environment-driven throughout, so the variable *names* are
    part of the contract with the deployment: a typo in a literal is a silent
    fallback to the default, which is exactly what a magic string costs here.
    Read values via ``EnvKey.<NAME>.value`` and keep the groups below in sync
    with `deployment/.env.*.example` and `docs/`.

    Not covered here: the names that already live on their own constants class
    in `constants.py` (``ModalBackend.KEY_ENV``/``SECRET_ENV``,
    ``ScalewayBackend.token_env``, ``ObstructionConcurrency.MAX_ENV``) or in a dedicated per-service map
    (``ServiceConfigMaps.ENV_VAR_MAP`` for the `*_SERVICE_URL` overrides). They
    belong to the component that reads them and that module stays
    dependency-light on purpose — duplicating them here would create a second
    source of truth, which is the very thing this enum exists to prevent.
    """

    # ── Runtime / process ───────────────────────────────────────────────────
    PORT = "PORT"
    DEPLOYMENT_MODE = "DEPLOYMENT_MODE"
    FLASK_DEBUG = "FLASK_DEBUG"
    API_DOCS_ENABLED = "API_DOCS_ENABLED"
    CORS_ORIGINS = "CORS_ORIGINS"

    # ── Pre-import environment setup (must be set before torch/tf/cv2 load) ─
    CUDA_VISIBLE_DEVICES = "CUDA_VISIBLE_DEVICES"
    TF_CPP_MIN_LOG_LEVEL = "TF_CPP_MIN_LOG_LEVEL"
    OPENCV_IO_ENABLE_OPENEXR = "OPENCV_IO_ENABLE_OPENEXR"
    OMP_NUM_THREADS = "OMP_NUM_THREADS"

    # ── Authentication ──────────────────────────────────────────────────────
    AUTH_TYPE = "AUTH_TYPE"
    API_TOKEN = "API_TOKEN"
    AUTH0_DOMAIN = "AUTH0_DOMAIN"
    AUTH0_AUDIENCE = "AUTH0_AUDIENCE"
    AUTH0_ALGORITHMS = "AUTH0_ALGORITHMS"

    # ── Shared Redis ────────────────────────────────────────────────────────
    REDIS_URL = "REDIS_URL"

    # ── Rate limiting ───────────────────────────────────────────────────────
    RATE_LIMIT_ENABLED = "RATE_LIMIT_ENABLED"
    RATE_LIMIT_PER_DAY = "RATE_LIMIT_PER_DAY"
    RATE_LIMIT_AUX_PER_DAY = "RATE_LIMIT_AUX_PER_DAY"
    RATE_LIMIT_WINDOW_HOURS = "RATE_LIMIT_WINDOW_HOURS"
    RATE_LIMIT_REDIS_URL = "RATE_LIMIT_REDIS_URL"
    RATE_LIMIT_KEY_PREFIX = "RATE_LIMIT_KEY_PREFIX"
    RATE_LIMIT_CLIENT_ID = "RATE_LIMIT_CLIENT_ID"
    RATE_LIMIT_TRUSTED_PROXY_HOPS = "RATE_LIMIT_TRUSTED_PROXY_HOPS"

    # ── Time-limited trial ──────────────────────────────────────────────────
    TRIAL_ENABLED = "TRIAL_ENABLED"
    TRIAL_CLIENT_ID = "TRIAL_CLIENT_ID"
    TRIAL_HOURS = "TRIAL_HOURS"
    TRIAL_REDIS_URL = "TRIAL_REDIS_URL"
    TRIAL_KEY_PREFIX = "TRIAL_KEY_PREFIX"
    TRIAL_ALLOW_LOCAL_STORE = "TRIAL_ALLOW_LOCAL_STORE"
