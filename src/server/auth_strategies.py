import hmac
import logging
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Any, Optional
from functools import wraps
from flask import request, g, has_app_context
import requests
import jwt
from jwt import PyJWK, PyJWTError
from .enums import ErrorType, AuthType
from .response_builder import ErrorResponseBuilder
from .auth_config import AuthConfig, Auth0Config

logger = logging.getLogger("logger")


class AuthenticationStrategy(ABC):
    """Abstract base class for authentication strategies using Adapter pattern"""

    def __init__(self):
        self._error_builder = ErrorResponseBuilder()

    @abstractmethod
    def validate_request(self, auth_header: Optional[str]) -> tuple[bool, Optional[ErrorType]]:
        """Validate the authentication header

        Args:
            auth_header: Authorization header value

        Returns:
            Tuple of (is_valid, error_type)
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if authentication is properly configured"""
        pass

    def require_auth(self, f: Callable) -> Callable:
        """Decorator to require authentication for a route

        Args:
            f: The route function to protect

        Returns:
            Decorated function with authentication
        """
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            auth_header = request.headers.get('Authorization')

            if not auth_header:
                self._log_rejection(ErrorType.MISSING_AUTHORIZATION)
                return self._error_builder.build(ErrorType.MISSING_AUTHORIZATION)

            is_valid, error_type = self.validate_request(auth_header)

            if not is_valid:
                self._log_rejection(error_type)
                return self._error_builder.build(error_type)

            return f(*args, **kwargs)

        return decorated_function

    @staticmethod
    def _log_rejection(error_type: Optional[ErrorType]) -> None:
        """Log a rejected request (never the credential itself)."""
        logger.warning(
            "Authentication rejected: %s path=%s remote=%s",
            error_type.value if error_type else "unknown",
            request.path,
            request.remote_addr,
        )


class TokenAuthenticationStrategy(AuthenticationStrategy):
    """Token-based authentication strategy"""

    def __init__(self, token: Optional[str]):
        super().__init__()
        self._token = token

    def is_configured(self) -> bool:
        """Check if token authentication is configured"""
        return self._token is not None and len(self._token) > 0

    def validate_request(self, auth_header: Optional[str]) -> tuple[bool, Optional[ErrorType]]:
        """Validate token-based authentication

        Args:
            auth_header: Authorization header value

        Returns:
            Tuple of (is_valid, error_type)
        """
        if not auth_header:
            return False, ErrorType.MISSING_AUTHORIZATION

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return False, ErrorType.INVALID_AUTH_FORMAT

        token = parts[1]

        if not self.is_configured():
            # Fail closed: without a configured token nothing can be validated.
            return False, ErrorType.INVALID_TOKEN

        if hmac.compare_digest(token.encode(), self._token.encode()):
            return True, None

        return False, ErrorType.INVALID_TOKEN


class JwksProvider:
    """Thread-safe JWKS cache with TTL and on-demand refresh for unknown ``kid``.

    Refetches when the cache is older than ``ttl_seconds`` or when a token names
    a ``kid`` not in the cached set (Auth0 key rotation). Refetches triggered by
    unknown kids are throttled by ``min_refresh_interval_seconds`` so forged
    tokens with random kids cannot turn the server into a JWKS request amplifier.
    """

    def __init__(
        self,
        jwks_url: str,
        ttl_seconds: float = 3600.0,
        min_refresh_interval_seconds: float = 60.0,
        timeout_seconds: float = 10.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._jwks_url = jwks_url
        self._ttl = ttl_seconds
        self._min_refresh_interval = min_refresh_interval_seconds
        self._timeout = timeout_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._jwks: Optional[dict] = None
        self._fetched_at: float = float("-inf")

    @property
    def cached(self) -> Optional[dict]:
        return self._jwks

    def seed(self, jwks: dict) -> None:
        """Pre-populate the cache (tests, or a JWKS fetched out of band)."""
        with self._lock:
            self._jwks = jwks
            self._fetched_at = self._clock()

    def get_key(self, kid: Optional[str]) -> Optional[dict]:
        """Return the JWK for ``kid``, refreshing the cache when stale or missing it.

        Raises:
            RuntimeError: If JWKS cannot be fetched and no cached copy exists
        """
        with self._lock:
            if self._is_expired():
                self._refresh()
            key = self._find(kid)
            if key is None and self._may_refresh_for_unknown_kid():
                self._refresh()
                key = self._find(kid)
            return key

    def _is_expired(self) -> bool:
        return self._jwks is None or self._clock() - self._fetched_at >= self._ttl

    def _may_refresh_for_unknown_kid(self) -> bool:
        return self._clock() - self._fetched_at >= self._min_refresh_interval

    def _find(self, kid: Optional[str]) -> Optional[dict]:
        for key in (self._jwks or {}).get('keys', []):
            if key.get('kid') == kid:
                return key
        return None

    def _refresh(self) -> None:
        try:
            response = requests.get(self._jwks_url, timeout=self._timeout)
            response.raise_for_status()
            self._jwks = response.json()
        except requests.RequestException as e:
            if self._jwks is None:
                raise RuntimeError(f"Failed to fetch JWKS: {e}")
            # Keep serving the last good key set during an Auth0 outage.
            logger.warning("JWKS refresh failed, keeping cached keys: %s", e)
        finally:
            self._fetched_at = self._clock()


class Auth0AuthenticationStrategy(AuthenticationStrategy):
    """Auth0 JWT-based authentication strategy using Adapter pattern"""

    def __init__(self, config: Auth0Config, jwks_provider: Optional[JwksProvider] = None):
        super().__init__()
        self._config = config
        self._jwks = jwks_provider or JwksProvider(config.jwks_url)

    def is_configured(self) -> bool:
        """Check if Auth0 is properly configured"""
        return self._config is not None

    def _get_signing_key(self, token: str) -> Any:
        """Get the JWKS signing key for token verification

        Args:
            token: JWT token

        Returns:
            Public key matching the token's kid

        Raises:
            ValueError: If signing key cannot be found
        """
        try:
            unverified_header = jwt.get_unverified_header(token)
        except PyJWTError as e:
            raise ValueError(f"Invalid token header: {e}")

        kid = unverified_header.get('kid')
        key = self._jwks.get_key(kid)
        if key is None:
            raise ValueError(f"Unable to find signing key for kid: {kid}")
        return PyJWK(key).key

    def validate_request(self, auth_header: Optional[str]) -> tuple[bool, Optional[ErrorType]]:
        """Validate Auth0 JWT token

        Args:
            auth_header: Authorization header value

        Returns:
            Tuple of (is_valid, error_type)
        """
        if not auth_header:
            return False, ErrorType.MISSING_AUTHORIZATION

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return False, ErrorType.INVALID_AUTH_FORMAT

        token = parts[1]

        try:
            signing_key = self._get_signing_key(token)

            # Verify and decode the token
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=self._config.algorithms,
                audience=self._config.audience,
                issuer=self._config.issuer,
                options={"require": ["exp", "iss", "aud"]},
            )

            # Expose the subject + authorized-party (client id) so downstream
            # concerns (per-user rate limiting, per-app policy) can key on the
            # authenticated identity/app without re-parsing. Guarded: validation
            # must not depend on a Flask app context existing.
            if has_app_context():
                g.auth_subject = payload.get("sub")
                g.auth_client_id = payload.get("azp")

            # Token is valid
            return True, None

        except jwt.ExpiredSignatureError:
            return False, ErrorType.EXPIRED_JWT
        except PyJWTError:
            return False, ErrorType.INVALID_JWT
        except Exception:
            return False, ErrorType.INVALID_JWT


class NoAuthenticationStrategy(AuthenticationStrategy):
    """No authentication strategy (allows all requests)"""

    def require_auth(self, f: Callable) -> Callable:
        return f

    def is_configured(self) -> bool:
        """Always returns True as no configuration is needed"""
        return True

    def validate_request(self, auth_header: Optional[str]) -> tuple[bool, Optional[ErrorType]]:
        """Always returns valid (no authentication)

        Args:
            auth_header: Authorization header value (ignored)

        Returns:
            Tuple of (True, None)
        """
        return True, None
