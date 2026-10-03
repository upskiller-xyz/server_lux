import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from flask import Flask
from flask_cors import CORS

from .enums import HTTPHeader
from .rate_limiter import HEADER_LIMIT, HEADER_REMAINING, HEADER_RESET

logger = logging.getLogger("logger")

CORS_ORIGINS_ENV = "CORS_ORIGINS"
ALLOW_ALL_ORIGINS = "*"

# The API is called with a bearer token (no cookies), so credentials stay off.
ALLOWED_METHODS: Tuple[str, ...] = ("GET", "POST", "OPTIONS")
ALLOWED_HEADERS: Tuple[str, ...] = (HTTPHeader.AUTHORIZATION.value, HTTPHeader.CONTENT_TYPE.value)
# The web app reads the quota from these headers; not readable cross-origin otherwise.
EXPOSED_HEADERS: Tuple[str, ...] = (HEADER_LIMIT, HEADER_REMAINING, HEADER_RESET)


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
        raw = os.getenv(CORS_ORIGINS_ENV, "")
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
            logger.warning(f"{CORS_ORIGINS_ENV} not set — CORS allows every origin")
        else:
            logger.info(f"CORS origins: {', '.join(self.origins)}")
        CORS(app, **self.flask_cors_options())
