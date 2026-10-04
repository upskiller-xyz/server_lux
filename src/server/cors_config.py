import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from flask import Flask
from flask_cors import CORS

from .enums import HTTPHeader
from .env_keys import EnvKey
from .rate_limiter import HEADER_LIMIT, HEADER_REMAINING, HEADER_RESET

logger = logging.getLogger("logger")

ALLOW_ALL_ORIGINS = "*"

# The API is called with a bearer token (no cookies), so credentials stay off.
ALLOWED_METHODS: Tuple[str, ...] = ("GET", "POST", "OPTIONS")
ALLOWED_HEADERS: Tuple[str, ...] = (HTTPHeader.AUTHORIZATION.value, HTTPHeader.CONTENT_TYPE.value)
# The web app reads the quota from these headers; not readable cross-origin otherwise.
# X-Request-Id: the correlation id echoed on responses, so a client-side report
# can join on the same id the backend's [call] records carry.
EXPOSED_HEADERS: Tuple[str, ...] = (
    HEADER_LIMIT,
    HEADER_REMAINING,
    HEADER_RESET,
    HTTPHeader.REQUEST_ID.value,
)


@dataclass(frozen=True)
class CorsConfig:
    """Cross-origin policy for the public API, built from ``CORS_ORIGINS``.

    ``CORS_ORIGINS`` is a comma-separated list of exact origins
    (``https://app.example.com``). Unset/empty keeps the legacy allow-all
    behaviour and logs a warning so it is visible in production logs.
    """

    origins: Tuple[str, ...]

    @classmethod
    def from_environment(cls) -> "CorsConfig":
        raw = os.getenv(EnvKey.CORS_ORIGINS.value, "")
        origins = tuple(origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip())
        return cls(origins or (ALLOW_ALL_ORIGINS,))

    @property
    def allows_all(self) -> bool:
        return ALLOW_ALL_ORIGINS in self.origins

    def flask_cors_options(self) -> Dict[str, Any]:
        return {
            "origins": list(self.origins),
            "methods": list(ALLOWED_METHODS),
            "allow_headers": list(ALLOWED_HEADERS),
            "expose_headers": list(EXPOSED_HEADERS),
            "supports_credentials": False,
        }

    def apply(self, app: Flask) -> None:
        if self.allows_all:
            logger.warning("%s not set — CORS allows every origin", EnvKey.CORS_ORIGINS.value)
        else:
            logger.info("CORS origins: %s", ', '.join(self.origins))
        CORS(app, **self.flask_cors_options())
